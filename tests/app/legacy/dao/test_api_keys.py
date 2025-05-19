"""Test for API keys DAO methods."""

from collections.abc import AsyncGenerator
from typing import Any, Awaitable, Callable, cast
from uuid import uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.db_init import get_write_session_with_context, metadata_legacy
from app.legacy.dao.api_keys_dao import LegacyApiKeysDao


@pytest.fixture
async def prepared_api_key(
    sample_service: Callable[[AsyncSession], Awaitable[Row[Any]]],
    sample_api_key: Callable[..., Awaitable[Row[Any]]],
) -> AsyncGenerator[Row[Any], None]:
    """Fixture that creates and yields a committed API key along with its associated service and user.

    This fixture is designed for integration tests that need a fully initialized API key record.
    It ensures database state is appropriately committed before the test, and it performs cleanup
    afterward by deleting the API key, service, and user rows from the legacy tables.

    Setup:
        - Creates a sample service, which implicitly creates a sample user.
        - Creates a sample API key associated with that service.
        - Commits the service and API key to the database.

    Teardown:
        - Deletes the API key, service, and user records from the legacy schema to maintain isolation.

    Args:
        sample_service (Callable): A factory fixture that returns a new service row.
        sample_api_key (Callable): A factory fixture that returns a new API key row for a given service.

    Yields:
        Row[Any]: A SQLAlchemy Core row representing the inserted API key.
    """
    # setup
    async with get_write_session_with_context() as raw_session:
        # cast the async_scoped_session[AsyncSession] to keep mypy happy
        session = cast(AsyncSession, raw_session)
        service = await sample_service(session)
        api_key = await sample_api_key(session, service_id=service.id)
        await session.commit()

    yield api_key

    # teardown
    legacy_users = metadata_legacy.tables['users']
    legacy_services = metadata_legacy.tables['services']
    legacy_api_keys = metadata_legacy.tables['api_keys']

    async with get_write_session_with_context() as raw_session:
        # cast the async_scoped_session[AsyncSession] to keep mypy happy
        session = cast(AsyncSession, raw_session)
        await session.execute(delete(legacy_api_keys).where(legacy_api_keys.c.id == api_key.id))
        await session.execute(delete(legacy_services).where(legacy_services.c.id == service.id))
        await session.execute(delete(legacy_users).where(legacy_users.c.id == service.created_by_id))
        await session.commit()


class TestLegacyApiKeysDao:
    """Integration tests for LegacyApiKeysDao methods using committed database records.

    These tests validate the behavior of API key-related DAO operations against
    the actual database schema, ensuring that keys are correctly persisted and retrieved
    without relying on mocks or in-memory substitutes.
    """

    async def test_get_api_keys(self, prepared_api_key: Row[Any]) -> None:
        """Test that API keys can be retrieved by service ID.

        Given a committed API key associated with a sample service (via the prepared_api_key fixture),
        this test verifies that LegacyApiKeysDao.get_api_keys correctly returns the expected key.

        Asserts:
            - Exactly one API key is returned for the service
            - The returned key's ID and name match the inserted key
        """
        keys = await LegacyApiKeysDao.get_api_keys(prepared_api_key.service_id)

        assert len(keys) == 1, 'prepared service should only have one api key'
        assert keys[0].id == prepared_api_key.id, 'api key ids should match'
        assert keys[0].name == prepared_api_key.name, 'api key names should match'

    async def test_get_api_keys_raises_if_not_found(self) -> None:
        """API keys should not exist for non-existant service."""
        keys = await LegacyApiKeysDao.get_api_keys(uuid4())

        assert len(keys) == 0, 'keys should not exist'
