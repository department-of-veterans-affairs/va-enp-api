"""App entrypoint."""

import os
from asyncio.exceptions import CancelledError
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, AsyncContextManager, Callable, Mapping, Never

from fastapi import Depends, FastAPI, status
from fastapi.staticfiles import StaticFiles
from loguru import logger
from pydantic import UUID4

from app.auth import JWTBearer
from app.db.db_init import (
    close_db,
    init_db,
)
from app.legacy.v2.notifications.rest import v2_legacy_notification_router, v2_notification_router
from app.logging.logging_config import CustomizeLogger
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


@asynccontextmanager
async def lifespan(app: CustomFastAPI) -> AsyncIterator[Never]:
    """Initialize the database, and populate the providers dictionary.

    https://fastapi.tiangolo.com/advanced/events/?h=life#lifespan

    Args:
        app: the app

    Yields:
        None: nothing

    """
    await init_db()

    try:
        yield  # type: ignore
    except CancelledError as e:
        if isinstance(e.__context__, KeyboardInterrupt):
            logger.info('Stopped app with a KeyboardInterrupt')
        else:
            logger.exception('Failed to gracefully stop the app')
    finally:
        app.enp_state.clear_providers()
        await close_db()
        logger.info('AsyncContextManager lifespan shutdown complete')


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


@app.get('/enp')
def simple_route() -> dict[str, str]:
    """Return a hello world.

    Returns:
        dict[str, str]: Hello World

    """
    logger.info('Hello World')
    return {'Hello': 'World'}


@app.get('/legacy/notifications/{notification_id}', status_code=status.HTTP_200_OK, dependencies=[Depends(JWTBearer())])
async def get_legacy_notification(notification_id: UUID4) -> None:
    """Get a legacy Notification.

    Args:
        notification_id (UUID4): id of the notification
    """
    from app.legacy.dao.notifications_dao import LegacyNotificationDao

    data = await LegacyNotificationDao.get_notification(notification_id)
    logger.info('Notification data: {}', data._asdict())
