"""App entrypoint."""

from fastapi import FastAPI

from app.logging.logging_config import CustomizeLogger
from app.v3.notifications.rest import notification_router


def create_app() -> FastAPI:
    """Create and configure the FastAPI app.

    Returns
    -------
    FastAPI: The FastAPI application instance

    """
    app = FastAPI()

    app.include_router(notification_router)
    app.logger = CustomizeLogger.make_logger()  # type: ignore

    return app


app: FastAPI = create_app()


@app.get('/')
def simple_route() -> dict[str, str]:
    """Return a hello world.

    Returns
    -------
        dict[str, str]: Hello World

    """
    app.logger.info('Hello World')
    return {'Hello': 'World'}
