"""App entrypoint."""

from fastapi import FastAPI

from app.v3.notifications.rest import notification_router

app = FastAPI()
app.include_router(notification_router)


@app.get('/')
def simple_route() -> dict[str, str]:
    """Return a hello world.

    Returns
    -------
        dict[str, str]: Hello World

    """
    return {'Hello': 'World'}
