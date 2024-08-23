"""App entrypoint."""

from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def simple_route() -> dict[str, str]:
    """Return a hello world.

    Returns
    -------
        dict[str, str]: Hello World

    """
    return {"Hello": "World"}
