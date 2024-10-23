"""App entrypoint."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Never

from fastapi import FastAPI
from loguru import logger

from app.legacy.v2.notifications.rest import v2_notification_router
from app.logging.logging_config import CustomizeLogger
from app.providers.provider_aws import ProviderAWS
from app.v3.notifications.rest import notification_router

# Route handlers should access this dictionary to send notifications using
# various third-party services, such as AWS, Twilio, etc.
providers = {}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[Never]:  # noqa: RUF029
    """Populate the providers dictionary.

    https://fastapi.tiangolo.com/advanced/events/?h=life#lifespan

    Args:
    ----
        app: the app

    Yields:
    ------
        None: nothing

    """
    providers['aws'] = ProviderAWS()
    yield  # type: ignore
    providers.clear()


def create_app() -> FastAPI:
    """Create and configure the FastAPI app.

    Returns:
        CustomFastAPI: The FastAPI application instance with custom logging.

    """
    CustomizeLogger.make_logger()
    app = FastAPI(lifespan=lifespan)
    app.include_router(notification_router)
    app.include_router(v2_notification_router)
    return app


app: FastAPI = create_app()


@app.get('/')
def simple_route() -> dict[str, str]:
    """Return a hello world.

    Returns
    -------
        dict[str, str]: Hello World

    """
    logger.info('Hello World')
    return {'Hello': 'World'}
