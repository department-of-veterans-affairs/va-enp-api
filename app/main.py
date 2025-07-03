"""App entrypoint."""

import os
import time
from asyncio.exceptions import CancelledError
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, AsyncContextManager, Callable, Mapping, Never

from fastapi import Depends, FastAPI, status
from fastapi.staticfiles import StaticFiles
from pydantic import UUID4
from starlette_context import plugins
from starlette_context.middleware import ContextMiddleware

from app.auth import JWTBearerAdmin
from app.clients.redis_client import RedisClientManager
from app.db.db_init import (
    close_db,
    init_db,
)
from app.legacy.v2.notifications.rest import v2_legacy_notification_router, v2_notification_router
from app.logging.logging_config import CustomizeLogger, logger
from app.state import ENPState
from app.v3 import api_router as v3_router

MKDOCS_DIRECTORY = 'site'


class CustomFastAPI(FastAPI):
    """Custom FastAPI class to include ENPState."""

    def __init__(self, lifespan: Callable[['CustomFastAPI'], AsyncContextManager[Mapping[str, Any]]]) -> None:
        """Initialize the CustomFastAPI instance with ENPState.

        Args:
            lifespan: The lifespan context manager for the application.
        """
        super().__init__(lifespan=lifespan)
        self.enp_state = ENPState()


async def _cleanup_lifespan_resources(app: CustomFastAPI, redis_manager: RedisClientManager, worker_id: int) -> None:
    """Clean up lifespan resources with proper error handling.

    Args:
        app: The FastAPI application instance
        redis_manager: The Redis client manager
        worker_id: The worker process ID
    """
    shutdown_start = time.time()
    logger.info(f'[Worker {worker_id}] Starting lifespan cleanup...')

    try:
        app.enp_state.clear_providers()
        logger.info(f'[Worker {worker_id}] Providers cleared')
    except Exception as e:
        logger.exception(f'[Worker {worker_id}] Error clearing providers: {e}')

    try:
        await close_db()
        logger.info(f'[Worker {worker_id}] Database connections closed')
    except Exception as e:
        logger.exception(f'[Worker {worker_id}] Error closing database: {e}')

    try:
        await redis_manager.close()
        logger.info(f'[Worker {worker_id}] Redis connections closed')
    except Exception as e:
        logger.exception(f'[Worker {worker_id}] Error closing Redis: {e}')

    shutdown_time = time.time() - shutdown_start
    logger.info(f'[Worker {worker_id}] AsyncContextManager lifespan shutdown complete in {shutdown_time:.2f}s')


@asynccontextmanager
async def lifespan(app: CustomFastAPI) -> AsyncIterator[Never]:
    """Initialize the database, and populate the providers dictionary.

    https://fastapi.tiangolo.com/advanced/events/?h=life#lifespan

    Args:
        app: the app

    Yields:
        None: nothing

    """
    worker_id = os.getpid()
    start_time = time.time()

    logger.info(f'[Worker {worker_id}] Starting lifespan initialization...')

    try:
        logger.info(f'[Worker {worker_id}] Initializing the RedisClientManager...')
        redis_url = os.getenv('REDIS_URL', 'redis://0.0.0.0:6379')
        redis_manager = RedisClientManager(redis_url)
        app.enp_state.redis_client_manager = redis_manager
        await redis_manager.get_client().ping()
        logger.info(f'[Worker {worker_id}] ...RedisClientManager initialized.')

        logger.info(f'[Worker {worker_id}] Initializing database...')
        await init_db()
        logger.info(f'[Worker {worker_id}] ...Database initialized.')

        init_time = time.time() - start_time
        logger.info(f'[Worker {worker_id}] Lifespan initialization completed in {init_time:.2f}s')

        try:
            yield  # type: ignore
        except CancelledError as e:
            if isinstance(e.__context__, KeyboardInterrupt):
                logger.info(f'[Worker {worker_id}] Stopped app with a KeyboardInterrupt')
            else:
                logger.exception(f'[Worker {worker_id}] Failed to gracefully stop the app')
        finally:
            await _cleanup_lifespan_resources(app, redis_manager, worker_id)

    except Exception as e:
        logger.exception(f'[Worker {worker_id}] Critical error during lifespan initialization: {e}')
        raise


def create_app() -> CustomFastAPI:
    """Create and configure the FastAPI app.

    Returns:
        CustomFastAPI: The FastAPI application instance with custom logging.
    """
    CustomizeLogger.make_logger()
    app = CustomFastAPI(lifespan=lifespan)
    app.include_router(v3_router)
    app.include_router(v2_legacy_notification_router)
    app.include_router(v2_notification_router)

    # Static site for MkDocs. If unavailable locally, run `mkdocs build` to create the site files,
    # or run the application locally with Docker.
    if os.path.exists(MKDOCS_DIRECTORY):
        app.mount('/mkdocs', StaticFiles(directory=MKDOCS_DIRECTORY, html=True), name='mkdocs')

    return app


app: CustomFastAPI = create_app()
app.add_middleware(
    ContextMiddleware,
    plugins=(plugins.RequestIdPlugin(force_new_uuid=False),),
)


@app.get('/enp')
def simple_route() -> dict[str, str]:
    """Return a hello world.

    Returns:
        dict[str, str]: Hello World

    """
    logger.info('Hello World')
    return {'Hello': 'World'}


@app.get(
    '/legacy/notifications/{notification_id}',
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(JWTBearerAdmin())],
)
async def get_legacy_notification(notification_id: UUID4) -> None:
    """Get a legacy Notification.

    Args:
        notification_id (UUID4): id of the notification
    """
    from app.legacy.dao.notifications_dao import LegacyNotificationDao

    data = await LegacyNotificationDao.get(notification_id)
    logger.info('Notification data: {}', data._asdict())


async def _check_redis_health(app: CustomFastAPI) -> dict[str, Any]:
    """Check Redis connection health.

    Returns:
        dict: Redis health status with 'status' and optional 'error' keys
    """
    redis_status = {'status': 'unknown', 'error': None}
    try:
        if app.enp_state.redis_client_manager:
            await app.enp_state.redis_client_manager.get_client().ping()
            redis_status['status'] = 'healthy'
        else:
            redis_status['status'] = 'not_initialized'
    except Exception as e:
        redis_status['status'] = 'error'
        redis_status['error'] = str(e)
    return redis_status


def _check_providers_health(app: CustomFastAPI) -> dict[str, Any]:
    """Check provider state health.

    Returns:
        dict: Provider health status with 'status' and 'count' keys
    """
    providers_status = {'status': 'unknown', 'count': 0}
    try:
        if hasattr(app.enp_state, 'providers'):
            providers_status['status'] = 'healthy'
            providers_status['count'] = len(getattr(app.enp_state, 'providers', {}))
        else:
            providers_status['status'] = 'not_initialized'
    except Exception as e:
        providers_status['status'] = 'error'
        providers_status['error'] = str(e)
    return providers_status


@app.get('/health/lifespan')
async def lifespan_health_check() -> dict[str, Any]:
    """Check the health of lifespan-initialized resources.

    Returns:
        dict: Health status of Redis, database, and provider state
    """
    health_status = {
        'worker_id': os.getpid(),
        'timestamp': time.time(),
        'redis': await _check_redis_health(app),
        'providers': _check_providers_health(app),
        'database': {'status': 'check_not_implemented', 'note': 'Add specific DB health check based on your DB setup'},
    }

    return health_status
