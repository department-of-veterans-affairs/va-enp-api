"""App entrypoint."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Never
from uuid import uuid4

from fastapi import Depends, FastAPI, status
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_scoped_session

from app.db.db_init import close_db, get_read_session, get_write_session, init_db
from app.db.models import Test
from app.legacy.v2.notifications.rest import v2_notification_router
from app.logging.logging_config import CustomizeLogger
from app.providers.provider_aws import ProviderAWS
from app.v3.notifications.rest import notification_router

# Route handlers should access this dictionary to send notifications using
# various third-party services, such as AWS, Twilio, etc.
providers = {}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[Never]:
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
    await init_db()
    yield  # type: ignore
    providers.clear()
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


@app.post('/db/test_post', status_code=status.HTTP_201_CREATED)
async def test_db_add(
    *,
    data: str | None = None,
    db_session: Annotated[async_scoped_session[AsyncSession], Depends(get_write_session)],
) -> dict[str, str]:
    """Test inserting into the database. This is a temporary test endpoint.

    Args:
    ----
        data (str | None): The data to insert
        db_session: The database session

    Returns:
    -------
        dict[str, str]: The inserted item

    """
    logger.info('Testing db insert...')
    item = {'id': str(uuid4()), 'data': data or 'test data'}
    test_item = Test(**item)
    async with db_session() as session:
        session.add(test_item)
        await session.commit()
        await session.refresh(test_item)
    return item


@app.get('/db/test_get', status_code=status.HTTP_200_OK)
async def test_db_get(
    db_session: Annotated[async_scoped_session[AsyncSession], Depends(get_read_session)],
) -> list[dict[str, str]]:
    """Test getting items from the database. This is a temporary test endpoint.

    Args:
    ----
        db_session: The database session

    Returns:
    -------
        list[dict[str,str]]: The first 10 items in the tests table

    """
    items = []
    logger.info('Testing db get...')
    async with db_session() as session:
        results = await session.execute(select(Test))
        for r in results:
            items.append({'id': str(r[0].id), 'data': r[0].data})
    return items
