"""App entrypoint."""

from typing import Any

from fastapi import FastAPI

from app.logging.logging_config import CustomizeLogger
from app.v3.notifications.rest import notification_router


class CustomFastAPI(FastAPI):
    """FastAPI subclass that integrates custom logging."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:  # noqa
        """Initialize the CustomFastAPI instance with custom logging.

        Args:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        """
        super(CustomFastAPI, self).__init__(*args, **kwargs)
        self.logger = CustomizeLogger.make_logger()


def create_app() -> CustomFastAPI:
    """Create and configure the FastAPI app.

    Returns:
        CustomFastAPI: The FastAPI application instance with custom logging.

    """
    app = CustomFastAPI()
    app.include_router(notification_router)
    return app


app: CustomFastAPI = create_app()


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
