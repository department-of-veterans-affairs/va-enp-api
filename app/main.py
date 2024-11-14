"""App entrypoint."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Never

from fastapi import Depends, FastAPI, status
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_scoped_session

from app.db.db_init import close_db, get_read_session_with_depends, get_write_session_with_depends, init_db
from app.legacy.v2.notifications.rest import v2_notification_router
from app.logging.logging_config import CustomizeLogger
from app.providers.provider_aws import ProviderAWS
from app.v3.notifications.rest import notification_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[Never]:
    """Initialize the database, and populate the providers dictionary.

    https://fastapi.tiangolo.com/advanced/events/?h=life#lifespan

    Args:
    ----
        app: the app

    Yields:
    ------
        None: nothing

    """
    await init_db()
    # Route handlers should access this dictionary to send notifications using
    # various third-party services, such as AWS, Twilio, etc.
    app.state.providers = {'aws': ProviderAWS()}

    yield  # type: ignore

    app.state.providers.clear()
    await close_db()


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


@app.post('/db/test', status_code=status.HTTP_201_CREATED)
async def test_db_create(
    *,
    data: str = 'hello',
    db_session: Annotated[async_scoped_session[AsyncSession], Depends(get_write_session_with_depends)],
) -> dict[str, str]:
    """Test inserting Templates into the database. This is a temporary test endpoint.

    Args:
    ----
        data (str): The data to insert
        db_session: The database session

    Returns:
    -------
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
    ----
        db_session: The database session

    Returns:
    -------
        list[dict[str,str]]: The items in the tests table

    """
    from app.db.models import Template

    items = []
    async with db_session() as session:
        results = await session.scalars(select(Template))
        for r in results:
            items.append({'id': str(r.id), 'name': r.name})
    return items
