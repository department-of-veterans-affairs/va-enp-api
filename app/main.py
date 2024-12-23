"""App entrypoint."""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any, AsyncContextManager, Callable, Mapping, Never

from fastapi import Depends, FastAPI, status
from fastapi.staticfiles import StaticFiles
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_scoped_session

from app.db.db_init import (
    close_db,
    get_read_session_with_depends,
    get_write_session_with_depends,
    init_db,
)
from app.legacy.v2.notifications.rest import v2_notification_router
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

    yield  # type: ignore

    app.enp_state.clear_providers()
    await close_db()


def create_app() -> CustomFastAPI:
    """Create and configure the FastAPI app.

    Returns:
        CustomFastAPI: The FastAPI application instance with custom logging.
    """
    CustomizeLogger.make_logger()
    app = CustomFastAPI(lifespan=lifespan)
    app.include_router(v3_router)
    app.include_router(v2_notification_router)

    # Static site for MkDocs. If unavailable locally, run `mkdocs build` to create the site files
    # Or run the application locally with Docker.
    if os.path.exists(MKDOCS_DIRECTORY):
        app.mount('/mkdocs', StaticFiles(directory=MKDOCS_DIRECTORY, html=True), name='mkdocs')

    return app


app: CustomFastAPI = create_app()


@app.get('/')
def simple_route() -> dict[str, str]:
    """Return a hello world.

    Returns:
        dict[str, str]: Hello World

    """
    logger.info('Hello World')
    return {'Hello': 'World'}


@app.post('/db/test', status_code=status.HTTP_201_CREATED)
async def test_db_create(
    *,
    data: str = 'hello',
    db_session: Annotated[async_scoped_session[AsyncSession], Depends(get_write_session_with_depends)],
) -> dict[str, str]:
    """Test inserting Templates into the database. This is a temporary test endpoint.

    Args:
        data (str): The data to insert
        db_session: The database session

    Returns:
        dict[str, str]: The inserted item

    """
    from app.db.models import Template

    template = Template(name=data)

    async with db_session() as session:
        session.add(template)
        await session.commit()
    return {
        'id': str(template.id),
        'name': template.name,
        'created_at': str(template.created_at),
        'updated_at': str(template.updated_at),
    }


@app.get('/db/test', status_code=status.HTTP_200_OK)
async def test_db_read(
    db_session: Annotated[async_scoped_session[AsyncSession], Depends(get_read_session_with_depends)],
) -> list[dict[str, str]]:
    """Test getting items from the database. This is a temporary test endpoint.

    Args:
        db_session: The database session

    Returns:
        list[dict[str,str]]: The items in the tests table

    """
    from app.db.models import Template

    items = []
    async with db_session() as session:
        results = await session.scalars(select(Template))
        for r in results:
            items.append({'id': str(r.id), 'name': r.name})
    return items
