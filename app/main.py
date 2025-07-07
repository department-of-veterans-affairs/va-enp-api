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
    logger.info(f'[Worker {worker_id}] *** STARTING LIFESPAN CLEANUP ***')

    try:
        logger.info(f'[Worker {worker_id}] Clearing providers...')
        app.enp_state.clear_providers()
        logger.info(f'[Worker {worker_id}] ✓ Providers cleared')
    except Exception as e:
        logger.exception(f'[Worker {worker_id}] ✗ Error clearing providers: {e}')

    try:
        logger.info(f'[Worker {worker_id}] Closing database connections...')
        await close_db()
        logger.info(f'[Worker {worker_id}] ✓ Database connections closed')
    except Exception as e:
        logger.exception(f'[Worker {worker_id}] ✗ Error closing database: {e}')

    try:
        logger.info(f'[Worker {worker_id}] Closing Redis connections...')
        await redis_manager.close()
        logger.info(f'[Worker {worker_id}] ✓ Redis connections closed')
    except Exception as e:
        logger.exception(f'[Worker {worker_id}] ✗ Error closing Redis: {e}')

    shutdown_time = time.time() - shutdown_start
    logger.info(f'[Worker {worker_id}] *** LIFESPAN CLEANUP COMPLETE in {shutdown_time:.2f}s ***')

    # Ensure logs are flushed before exit
    import sys

    sys.stdout.flush()
    sys.stderr.flush()


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
                logger.info(f'[Worker {worker_id}] *** SHUTDOWN INITIATED: KeyboardInterrupt ***')
            else:
                logger.exception(f'[Worker {worker_id}] *** SHUTDOWN INITIATED: CancelledError ***')
        except Exception as e:
            logger.exception(f'[Worker {worker_id}] *** SHUTDOWN INITIATED: Exception: {e} ***')
        finally:
            logger.info(f'[Worker {worker_id}] *** ENTERING LIFESPAN CLEANUP ***')
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
    logger.info('*** TRIGGERING GRACEFUL EXIT ***')
    import os
    import signal
    import sys
    import time

    # Add a small delay to ensure the log is flushed
    time.sleep(0.1)

    # Try sending SIGTERM to self for more graceful shutdown
    try:
        logger.info('Sending SIGTERM to self for graceful shutdown...')
        os.kill(os.getpid(), signal.SIGTERM)
        time.sleep(1)  # Give it time to process
    except Exception as e:
        logger.warning(f'SIGTERM failed: {e}, falling back to sys.exit')

    # Fallback to sys.exit
    logger.info('Falling back to sys.exit...')
    sys.exit(1)


def _trigger_kill() -> None:
    """Trigger hard kill."""
    logger.info('Triggering hard kill...')
    import os

    os._exit(1)


def _trigger_exception() -> None:
    """Trigger simulated exception cleanup test.

    This simulates what happens during an exception-based shutdown
    without actually crashing the worker process.
    """
    logger.info('*** TRIGGERING SIMULATED EXCEPTION CLEANUP ***')
    import asyncio
    import time

    time.sleep(0.1)  # Brief delay for log flush

    # Simulate the cleanup process that would happen during shutdown
    async def simulate_cleanup() -> None:
        worker_id = os.getpid()
        logger.info(f'[Worker {worker_id}] *** SIMULATING EXCEPTION SHUTDOWN ***')

        # Get the current app instance and redis manager
        if hasattr(app, 'enp_state') and app.enp_state.redis_client_manager:
            await _cleanup_lifespan_resources(app, app.enp_state.redis_client_manager, worker_id)
        else:
            logger.warning('Cannot simulate cleanup - app state not available')

    # Run the simulation
    try:
        asyncio.run(simulate_cleanup())
    except Exception as e:
        logger.exception(f'Error during cleanup simulation: {e}')

    # Return normally instead of crashing


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
    """Trigger simulated interrupt cleanup test.

    This simulates what happens during a keyboard interrupt shutdown
    without actually crashing the worker process.
    """
    logger.info('*** TRIGGERING SIMULATED INTERRUPT CLEANUP ***')
    import asyncio
    import time

    time.sleep(0.1)  # Brief delay for log flush

    # Simulate the cleanup process that would happen during shutdown
    async def simulate_cleanup() -> None:
        worker_id = os.getpid()
        logger.info(f'[Worker {worker_id}] *** SIMULATING INTERRUPT SHUTDOWN ***')

        # Get the current app instance and redis manager
        if hasattr(app, 'enp_state') and app.enp_state.redis_client_manager:
            await _cleanup_lifespan_resources(app, app.enp_state.redis_client_manager, worker_id)
        else:
            logger.warning('Cannot simulate cleanup - app state not available')

    # Run the simulation
    try:
        asyncio.run(simulate_cleanup())
    except Exception as e:
        logger.exception(f'Error during cleanup simulation: {e}')

    # Return normally instead of crashing


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
        'real_crash': _trigger_real_crash,
    }

    trigger = death_triggers.get(action)
    if trigger:
        trigger()


def _trigger_real_crash() -> None:
    """Trigger a real worker crash to test actual lifespan cleanup execution.

    This will actually crash the worker to verify that the lifespan cleanup
    gets called in real ungraceful shutdown scenarios.
    """
    logger.info('*** TRIGGERING REAL CRASH TEST ***')
    import os
    import time

    time.sleep(0.1)  # Brief delay for log flush

    # Log the worker ID for tracking
    worker_id = os.getpid()
    logger.info(f'[Worker {worker_id}] About to crash - watch for lifespan cleanup logs!')

    # Force immediate termination to test cleanup
    os._exit(1)


@app.get('/enp')
def simple_route(action: str = 'hello') -> dict[str, str]:
    """Return a hello world or trigger worker death for testing.

    Args:
        action: Action to perform. Options:
            - 'hello': Normal hello world response
            - 'exit': Graceful exit (calls sys.exit)
            - 'kill': Hard kill (os._exit)
            - 'exception': Simulated exception cleanup (safe)
            - 'segfault': Segmentation fault (ctypes)
            - 'memory': Memory exhaustion
            - 'interrupt': Simulated interrupt cleanup (safe)
            - 'real_crash': Real ungraceful crash (for testing actual lifespan)

    Returns:
        dict[str, str]: Hello World response or available actions list

    """
    logger.info(f'Hello World - action: {action}')

    if action == 'hello':
        return {'Hello': 'World'}

    if action in ['exit', 'kill', 'exception', 'segfault', 'memory', 'interrupt', 'real_crash']:
        _trigger_worker_death(action)
        return {'status': 'should_not_reach_here'}  # This won't be reached for exit/kill

    return {'Hello': 'World', 'available_actions': 'hello,exit,kill,exception,segfault,memory,interrupt,real_crash'}


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
