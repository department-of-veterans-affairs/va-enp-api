"""Fixtures and setup and teardown prepared/committed sample objects."""

from collections.abc import AsyncGenerator
from typing import Any, Awaitable, Callable

import pytest
from sqlalchemy import Row, delete
from sqlalchemy.ext.asyncio import AsyncSession, async_scoped_session

from app.db.db_init import get_write_session_with_context, metadata_legacy


@pytest.fixture
async def commit_service(
    sample_service: Callable[[async_scoped_session[AsyncSession]], Awaitable[Row[Any]]],
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
    async with get_write_session_with_context() as session:
        service = await sample_service(session)
        await session.commit()

    yield service

    # teardown
    legacy_users = metadata_legacy.tables['users']
    legacy_services = metadata_legacy.tables['services']

    async with get_write_session_with_context() as session:
        await session.execute(delete(legacy_services).where(legacy_services.c.id == service.id))
        await session.execute(delete(legacy_users).where(legacy_users.c.id == service.created_by_id))
        await session.commit()


@pytest.fixture
async def commit_template(
    commit_service: Row[Any],
    sample_template: Callable[..., Awaitable[Row[Any]]],
) -> AsyncGenerator[Row[Any], None]:
    """Fixture that creates, commits, and yields a sample template row for integration tests.

    This fixture is intended for DAO-level tests that require a fully persisted template row.
    It ensures that the template and its related user/service are committed to the database,
    and then cleans up both template records after the test to preserve database isolation.

    Setup:
        - Uses `commit_service` to provide a committed service and user.
        - Invokes the `sample_template` factory to create a template and template history.
        - Commits the template to the database so it is queryable in test logic.

    Teardown:
        - Deletes the template and its history from the legacy schema after the test completes.
        - The committed service and user are cleaned up by the `commit_service` fixture.

    Args:
        commit_service (Row[Any]): A committed service row with associated user data.
        sample_template (Callable[..., Awaitable[Row[Any]]]): A coroutine factory that creates a template row.

    Yields:
        Row[Any]: A SQLAlchemy Core row representing the inserted template.
    """
    # setup
    async with get_write_session_with_context() as session:
        template = await sample_template(session=session, service_id=commit_service.id)
        await session.commit()

    yield template

    # teardown
    legacy_templates = metadata_legacy.tables['templates']
    legacy_templates_hist = metadata_legacy.tables['templates_history']

    async with get_write_session_with_context() as session:
        await session.execute(delete(legacy_templates_hist).where(legacy_templates_hist.c.id == template.id))
        await session.execute(delete(legacy_templates).where(legacy_templates.c.id == template.id))
        await session.commit()


@pytest.fixture
async def commit_service_sms_sender(
    commit_service: Row[Any],
    sample_service_sms_sender: Callable[..., Awaitable[Row[Any]]],
) -> AsyncGenerator[Row[Any], None]:
    """Fixture that creates, commits, and yields a sample service_sms_sender row for integration tests.

    This fixture is intended for DAO-level tests that require a fully persisted service_sms_sender row.
    It ensures that the service_sms_sender is committed to the database and then
    cleans up the record after the test to preserve database isolation.

    Setup:
        - Invokes the `sample_service_sms_sender` factory to create a service_sms_sender.
        - Commits the service_sms_sender to the database so it is queryable in test logic.

    Teardown:
        - Deletes the service_sms_sender from the legacy schema after the test completes.

    Args:
        commit_service (Row[Any]): A fixture that provides a committed service row.
        sample_service_sms_sender (Callable): A coroutine factory that creates and returns a service row.

    Yields:
        Row[Any]: A SQLAlchemy Core row representing the inserted service_sms_sender.
    """
    # setup
    async with get_write_session_with_context() as session:
        sms_sender = await sample_service_sms_sender(commit_service.id, session)
        await session.commit()

    yield sms_sender

    # teardown
    legacy_sms_sender = metadata_legacy.tables['service_sms_senders']

    async with get_write_session_with_context() as session:
        await session.execute(delete(legacy_sms_sender).where(legacy_sms_sender.c.id == sms_sender.id))
        await session.commit()


@pytest.fixture
async def prepared_api_key(
    sample_service: Callable[[async_scoped_session[AsyncSession]], Awaitable[Row[Any]]],
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
    async with get_write_session_with_context() as session:
        service = await sample_service(session)
        api_key = await sample_api_key(session, service_id=service.id)
        await session.commit()

    yield api_key

    # teardown
    legacy_users = metadata_legacy.tables['users']
    legacy_services = metadata_legacy.tables['services']
    legacy_api_keys = metadata_legacy.tables['api_keys']

    async with get_write_session_with_context() as session:
        await session.execute(delete(legacy_api_keys).where(legacy_api_keys.c.id == api_key.id))
        await session.execute(delete(legacy_services).where(legacy_services.c.id == service.id))
        await session.execute(delete(legacy_users).where(legacy_users.c.id == service.created_by_id))
        await session.commit()
