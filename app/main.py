"""App entrypoint."""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated, Any, AsyncContextManager, Callable, List, Mapping, Never

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.staticfiles import StaticFiles
from loguru import logger
from sqlalchemy import extract, select
from sqlalchemy.ext.asyncio import AsyncSession, async_scoped_session

from app.db.db_init import (
    close_db,
    get_read_session_with_depends,
    get_write_session_with_depends,
    init_db,
)
from app.db.models import Notification, Template
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
) -> dict[str, list[dict[str, str]]]:
    """Test inserting Templates and Notifications into the database. This is a temporary test endpoint.

    Args:
        data (str): The data to insert
        db_session: The database session

    Returns:
        dict[str, dict[str, str]]: The inserted notification and template items

    """
    from app.db.models import Template

    template = Template(name=data)
    notification_2024 = Notification(personalization='2024 Notification', created_at=datetime(2024, 6, 15, 12, 0, 0))
    notification_2025 = Notification(personalization='2025 Notification', created_at=datetime(2025, 6, 15, 12, 0, 0))
    notification_2026 = Notification(personalization='2026 Notification', created_at=datetime(2026, 6, 15, 12, 0, 0))

    async with db_session() as session:
        session.add_all([template, notification_2024, notification_2025, notification_2026])
        await session.commit()

    return {
        'templates': [
            {
                'id': str(template.id),
                'name': str(template.name),
                'created_at': str(template.created_at),
                'updated_at': str(template.updated_at),
            }
        ],
        'notifications': [
            {
                'id': str(notification_2024.id),
                'personalization': str(notification_2024.personalization),
                'created_at': str(notification_2024.created_at),
                'updated_at': str(notification_2024.updated_at),
            },
            {
                'id': str(notification_2025.id),
                'personalization': str(notification_2025.personalization),
                'created_at': str(notification_2025.created_at),
                'updated_at': str(notification_2025.updated_at),
            },
            {
                'id': str(notification_2026.id),
                'personalization': str(notification_2026.personalization),
                'created_at': str(notification_2026.created_at),
                'updated_at': str(notification_2026.updated_at),
            },
        ],
    }


async def fetch_templates(session: AsyncSession) -> List[dict[str, str]]:
    """Fetch all templates from the database.

    Args:
        session (AsyncSession): The database session.

    Returns:
        List[dict[str, str]]: A list of templates, each represented as a dictionary.
    """
    templates = []
    results = await session.scalars(select(Template))
    for r in results:
        templates.append(
            {
                'type': 'template',
                'id': str(r.id),
                'name': r.name,
                'created_at': str(r.created_at),
                'updated_at': str(r.updated_at),
            }
        )
    return templates


async def fetch_notifications(session: AsyncSession, year_list: List[int]) -> List[dict[str, str]]:
    """Fetch notifications from the database, filtered by year if specified.

    Args:
        session (AsyncSession): The database session.
        year_list (List[int]): A list of years to filter notifications by. If empty, fetches all notifications.

    Returns:
        List[dict[str, str]]: A list of notifications, each represented as a dictionary.
    """
    notifications = []
    if year_list:
        notification_query = select(Notification).where(extract('year', Notification.created_at).in_(year_list))
    else:
        notification_query = select(Notification)

    results = await session.scalars(notification_query)
    for n in results:
        notifications.append(
            {
                'type': 'notification',
                'id': str(n.id),
                'personalization': n.personalization or '',
                'created_at': str(n.created_at),
                'updated_at': str(n.updated_at),
            }
        )
    return notifications


@app.get('/db/test', status_code=status.HTTP_200_OK)
async def test_db_read(
    db_session: Annotated[async_scoped_session[AsyncSession], Depends(get_read_session_with_depends)],
    years: str | None = Query(
        default=None, description='Comma-separated years to filter notifications (e.g., 2024,2025)'
    ),
) -> list[dict[str, str]]:
    """Get items from the database, including Templates and Notifications.

    Optionally filter notifications by multiple years passed as a comma-separated string (&years=2024,2025).

    Args:
        db_session (Annotated[async_scoped_session[AsyncSession]]): The database session dependency.
        years (str | None): Comma-separated years to filter notifications (optional).

    Returns:
        list[dict[str, str]]: The items in the Templates and Notifications tables.

    Raises:
        HTTPException: If the `years` parameter contains invalid values.
    """
    year_list: List[int] = []
    if years:
        try:
            year_list = [int(year.strip()) for year in years.split(',')]
        except ValueError:
            raise HTTPException(
                status_code=400, detail='Invalid years format. Use comma-separated integers (e.g., 2024,2025).'
            )

    items = []

    async with db_session() as session:
        items.extend(await fetch_templates(session))
        items.extend(await fetch_notifications(session, year_list))

    return items
