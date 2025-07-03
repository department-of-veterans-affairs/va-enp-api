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


def _trigger_exit() -> None:
    """Trigger graceful exit."""
    logger.info('Triggering graceful exit...')
    import sys

    sys.exit(1)


def _trigger_kill() -> None:
    """Trigger hard kill."""
    logger.info('Triggering hard kill...')
    import os

    os._exit(1)


def _trigger_exception() -> None:
    """Trigger unhandled exception.

    Raises:
        RuntimeError: Test exception to kill worker
    """
    logger.info('Triggering unhandled exception...')
    raise RuntimeError('Test exception to kill worker')


def _trigger_segfault() -> None:
    """Trigger segmentation fault."""
    logger.info('Triggering segmentation fault...')
    import ctypes

    ctypes.string_at(0)


def _trigger_memory() -> None:
    """Trigger memory exhaustion."""
    logger.info('Triggering memory exhaustion...')
    # This will gradually consume memory until the worker is killed
    data = []
    while True:
        data.append('x' * 1024 * 1024)  # 1MB chunks


def _trigger_interrupt() -> None:
    """Trigger keyboard interrupt.

    Raises:
        KeyboardInterrupt: Test keyboard interrupt
    """
    logger.info('Triggering keyboard interrupt...')
    raise KeyboardInterrupt('Test keyboard interrupt')


def _trigger_worker_death(action: str) -> None:
    """Trigger various worker death scenarios for testing lifespan cleanup.

    Args:
        action: The death scenario to trigger
    """
    death_triggers = {
        'exit': _trigger_exit,
        'kill': _trigger_kill,
        'exception': _trigger_exception,
        'segfault': _trigger_segfault,
        'memory': _trigger_memory,
        'interrupt': _trigger_interrupt,
    }

    trigger = death_triggers.get(action)
    if trigger:
        trigger()


@app.get('/enp')
def simple_route(action: str = 'hello') -> dict[str, str]:
    """Return a hello world or trigger worker death for testing.

    Args:
        action: Action to perform. Options:
            - 'hello': Normal hello world response
            - 'exit': Graceful exit (calls sys.exit)
            - 'kill': Hard kill (os._exit)
            - 'exception': Unhandled exception
            - 'segfault': Segmentation fault (ctypes)
            - 'memory': Memory exhaustion
            - 'interrupt': Keyboard interrupt simulation

    Returns:
        dict[str, str]: Hello World response or available actions list

    """
    logger.info(f'Hello World - action: {action}')

    if action == 'hello':
        return {'Hello': 'World'}

    if action in ['exit', 'kill', 'exception', 'segfault', 'memory', 'interrupt']:
        _trigger_worker_death(action)
        return {'status': 'should_not_reach_here'}  # This won't be reached

    return {'Hello': 'World', 'available_actions': 'hello,exit,kill,exception,segfault,memory,interrupt'}


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
