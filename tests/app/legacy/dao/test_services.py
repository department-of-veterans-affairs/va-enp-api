"""Tests for services DAO methods."""

from collections.abc import AsyncGenerator
from typing import Any, Awaitable, Callable, cast
from uuid import uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.engine import Row
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.db_init import get_write_session_with_context, metadata_legacy
from app.legacy.dao.services_dao import LegacyServiceDao


@pytest.fixture
async def prepared_service(
    sample_service: Callable[[AsyncSession], Awaitable[Row[Any]]],
) -> AsyncGenerator[Row[Any], None]:
    """Fixture that creates, commits, and yields a sample service row for integration tests.

    This fixture is intended for DAO-level tests that require a fully persisted service row.
    It ensures that the service and its related user are committed to the database and then
    cleans up both records after the test to preserve database isolation.

    Setup:
        - Invokes the `sample_service` factory to create a service and its related user.
        - Commits the service to the database so it is queryable in test logic.

    Teardown:
        - Deletes the service and user from the legacy schema after the test completes.

    Args:
        sample_service (Callable): A coroutine factory that creates and returns a service row.

    Yields:
        Row[Any]: A SQLAlchemy Core row representing the inserted service.
    """
    # setup
    async with get_write_session_with_context() as raw_session:
        # cast the async_scoped_session[AsyncSession] to keep mypy happy
        session = cast(AsyncSession, raw_session)
        service = await sample_service(session)
        await session.commit()

    yield service

    # teardown
    legacy_users = metadata_legacy.tables['users']
    legacy_services = metadata_legacy.tables['services']

    async with get_write_session_with_context() as raw_session:
        # cast the async_scoped_session[AsyncSession] to keep mypy happy
        session = cast(AsyncSession, raw_session)
        await session.execute(delete(legacy_services).where(legacy_services.c.id == service.id))
        await session.execute(delete(legacy_users).where(legacy_users.c.id == service.created_by_id))
        await session.commit()


class TestLegacyServiceDao:
    """Integration tests for LegacyServiceDao methods using committed database records.

    These tests validate the behavior of service-related DAO operations against
    the actual database schema and logic, rather than mocking or in-memory objects.
    """

    async def test_get_service(self, prepared_service: Row[Any]) -> None:
        """Test that a service can be retrieved from the database by ID.

        Given a committed service record (via the prepared_service fixture),
        this test verifies that LegacyServiceDao.get_service_by_id returns
        the correct row from the database.

        Asserts:
            - The retrieved service ID matches the inserted service ID.
        """
        service = await LegacyServiceDao.get_service(prepared_service.id)

        assert service.id == prepared_service.id, 'service should exist in database'

    async def test_get_service_raises_if_not_found(self) -> None:
        """Should raise NoResultFound when service does not exist in DB."""
        with pytest.raises(NoResultFound):
            await LegacyServiceDao.get_service(uuid4())
