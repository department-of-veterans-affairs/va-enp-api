"""Fixtures and setup to test the app."""

from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Callable
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
import pytest_asyncio
from pydantic import UUID4
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import NotificationType
from app.db.db_init import close_db, get_db_session, init_db


@pytest_asyncio.fixture(loop_scope='session', scope='session', autouse=True)
async def test_init_db() -> AsyncGenerator[None, None]:
    """At the start of testing, create async engines for read-only and read-write database access.

    Dispose of the engines when testing concludes.  These actions resemble the "lifespan" steps
    in main.py.

    The database server should be running and accepting connections.
    """
    await init_db(True)
    yield
    await close_db()


@pytest.fixture
async def test_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a transactional, read-write database session.

    Tests that use this fixture should not need to worry about rolling back database changes.
    """
    # _engine_napi_write will always be None if imported at the top.
    from app.db.db_init import _engine_napi_write

    assert _engine_napi_write is not None, 'This should have been initialized by the test_init_db fixture.'

    async with _engine_napi_write.connect() as connection:
        # Begin a transaction.
        async with connection.begin():
            session_maker = get_db_session(_engine_napi_write, 'write')
            async with session_maker() as session:
                yield session
        # A rollback should occur automatically because the "begin" block doesn't manually commit.


@pytest.fixture
def mock_template() -> Callable[..., AsyncMock]:
    """Return a Callable that returns a mock of a template that would be returned from the notification api db."""

    def _create_mock_template(
        id: UUID4 = uuid4(),
        name: str = 'test_template',
        template_type: NotificationType = NotificationType.SMS,
        created_at: datetime = datetime.now(timezone.utc),
        updated_at: datetime = datetime.now(timezone.utc),
        content: str = 'test content',
        service_id: UUID4 = uuid4(),
        subject: str = 'test subject',
        created_by_id: UUID4 = uuid4(),
        version: int = 1,
        archived: bool = False,
        process_type: str = 'p_type',
        hidden: bool = False,
        provider_id: UUID4 = uuid4(),
        communication_item_id: UUID4 = uuid4(),
        reply_to_email_address: str = 'test@mail.com',
        onsite_notification: bool = False,
        content_as_html: str = '<html><body>test content as html</body></html>',
        content_as_plain_text: str = 'test content as plain text',
    ) -> AsyncMock:
        """Return a mock template."""
        mock_template = AsyncMock()
        mock_template.id = id
        mock_template.name = name
        mock_template.template_type = template_type
        mock_template.created_at = created_at
        mock_template.updated_at = updated_at
        mock_template.content = content
        mock_template.service_id = service_id
        mock_template.subject = subject
        mock_template.created_by_id = created_by_id
        mock_template.version = version
        mock_template.archived = archived
        mock_template.process_type = process_type
        mock_template.hidden = hidden
        mock_template.provider_id = provider_id
        mock_template.communication_item_id = communication_item_id
        mock_template.reply_to_email_address = reply_to_email_address
        mock_template.onsite_notification = onsite_notification
        mock_template.content_as_html = content_as_html
        mock_template.content_as_plain_text = content_as_plain_text

        return mock_template

    return _create_mock_template
