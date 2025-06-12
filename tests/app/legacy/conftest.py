"""Pytest setup for all legacy code."""

from datetime import datetime, timezone
from random import randint
from typing import Any, Awaitable, Callable, Coroutine
from uuid import uuid4

import pytest
from pydantic import UUID4
from sqlalchemy import Row, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import NotificationType
from app.db.db_init import metadata_legacy
from tests.app.legacy.dao.test_api_keys import encode_and_sign


@pytest.fixture
def sample_user(
    no_commit_session: AsyncSession,
) -> Callable[..., Awaitable[Row[Any]]]:
    """Generates a sample User - Does not commit to the database.

    Args:
        no_commit_session (AsyncSession): A non-commit test session

    Returns:
        Callable[..., Awaitable[Row[Any]]]: The function to create a User
    """

    async def _wrapper(
        session: AsyncSession | None = None,
        id: UUID4 | None = None,
        name: str | None = None,
        email_address: str | None = None,
        created_at: datetime | None = None,
        failed_login_count: int = 0,
        state: str = 'pending',
        platform_admin: bool = False,
        blocked: bool = False,
    ) -> Row[Any]:
        id = id or uuid4()
        session = session or no_commit_session
        legacy_users = metadata_legacy.tables['users']

        # No need for the values to be in a separate dictionary because they have all the data already
        insert_stmt = insert(legacy_users).values(
            id=id,
            name=name or f'sample-user-{id}',
            email_address=email_address or f'create-user-{id}@va.gov',
            created_at=created_at or datetime.now(timezone.utc),
            failed_login_count=failed_login_count,
            state=state,
            platform_admin=platform_admin,
            blocked=blocked,
        )
        await session.execute(insert_stmt)
        select_stmt = select(legacy_users).where(legacy_users.c.id == id)
        return (await session.execute(select_stmt)).one()

    return _wrapper


@pytest.fixture
def sample_service(
    no_commit_session: AsyncSession,
    sample_user: Callable[..., Awaitable[Row[Any]]],
) -> Callable[..., Awaitable[Row[Any]]]:
    """Generates a sample Service - Does not commit to the database.

    Args:
        no_commit_session (AsyncSession): A non-commit test session
        sample_user (Callable[..., Awaitable[Row[Any]]]): Generator fixture for Users

    Returns:
        Callable[..., Awaitable[Row[Any]]]: The function to create a Service
    """

    async def _wrapper(
        session: AsyncSession | None = None,
        id: UUID4 | None = None,
        name: str | None = None,
        created_at: datetime | None = None,
        active: bool = True,
        message_limit: int = 1000,
        restricted: bool = False,
        research_mode: bool = False,
        created_by_id: UUID4 | None = None,  # Expecting a FK to this if it is here
        prefix_sms: bool = False,
        rate_limit: int = 3000,
        count_as_live: bool = True,
        version: int = 0,
    ) -> Row[Any]:
        id = id or uuid4()
        session = session or no_commit_session
        legacy_services = metadata_legacy.tables['services']
        data = {
            'id': id,
            'name': name or f'sample-service-{id}',
            'created_at': created_at or datetime.now(timezone.utc),
            'active': active,
            'message_limit': message_limit,
            'restricted': restricted,
            'research_mode': research_mode,
            'created_by_id': created_by_id,
            'prefix_sms': prefix_sms,
            'rate_limit': rate_limit,
            'count_as_live': count_as_live,
            'version': version,
        }

        if created_by_id is None:
            user = await sample_user(session, uuid4())
            data['created_by_id'] = user.id

        # Insert without commit
        insert_stmt = insert(legacy_services).values(**data)
        await session.execute(insert_stmt)

        # Get the new object
        select_stmt = select(legacy_services).where(legacy_services.c.id == id)
        return (await session.execute(select_stmt)).one()

    return _wrapper


@pytest.fixture
def sample_api_key(
    no_commit_session: AsyncSession,
    sample_service: Callable[..., Awaitable[Row[Any]]],
) -> Callable[..., Awaitable[Row[Any]]]:
    """Generates a sample API Key - Does not commit to the database.

    Args:
        no_commit_session (AsyncSession): A non-commit test session
        sample_service (Callable[..., Awaitable[Row[Any]]]): Generator fixture for Services

    Returns:
        Callable[..., Awaitable[Row[Any]]]:: The function to create a Service
    """

    async def _wrapper(
        session: AsyncSession | None = None,
        id: UUID4 | None = None,
        name: str | None = None,
        secret: str | None = None,
        service_id: UUID4 | None = None,
        key_type: str = 'normal',
        revoked: bool = False,
        expiry_date: datetime | None = None,
        created_at: datetime | None = None,
        created_by_id: UUID4 | None = None,
        version: int = 0,
    ) -> Row[Any]:
        id = id or uuid4()
        session = session or no_commit_session
        legacy_api_keys = metadata_legacy.tables['api_keys']
        legacy_key_type = metadata_legacy.tables['key_types']
        data = {
            'id': id,
            'name': name or f'sample-api-key-{id}',
            'secret': encode_and_sign(secret) if secret else encode_and_sign(f'secret-{id}'),
            'service_id': service_id,
            'key_type': key_type,
            'revoked': revoked,
            'expiry_date': expiry_date or datetime.now(timezone.utc),
            'created_at': created_at or datetime.now(timezone.utc),
            'created_by_id': created_by_id,
            'version': version,
        }

        if service_id is None:
            service = await sample_service(session, uuid4())
            data['service_id'] = service.id
        else:
            legacy_services = metadata_legacy.tables['services']
            select_service_stmt = select(legacy_services).where(legacy_services.c.id == service_id)
            service = (await session.execute(select_service_stmt)).one()

        data['created_by_id'] = created_by_id or service.created_by_id
        select_key_type_stmt = select(legacy_key_type).where(legacy_key_type.c.name == (key_type or 'normal'))
        data['key_type'] = (await session.execute(select_key_type_stmt)).one().name

        # Insert without commit
        insert_stmt = insert(legacy_api_keys).values(**data)
        await session.execute(insert_stmt)

        # Get the new object
        select_stmt = select(legacy_api_keys).where(legacy_api_keys.c.id == id)
        api_key = (await session.execute(select_stmt)).one()
        return api_key

    return _wrapper


@pytest.fixture
def sample_template(
    no_commit_session: AsyncSession,
    sample_service: Callable[..., Awaitable[Row[Any]]],
) -> Callable[..., Coroutine[Any, Any, Row[Any]]]:
    """Generates a sample Template - Does not commit to the database.

    Args:
        no_commit_session (AsyncSession): A non-commit test session
        sample_service (Callable[..., Awaitable[Row[Any]]]): Generator fixture for Services

    Returns:
        Callable[..., Coroutine[Any, Any, AsyncGenerator[Any, Row[Any]]]]: The function to create a Service
    """

    async def _wrapper(
        session: AsyncSession | None = None,
        id: UUID4 | None = None,
        name: str | None = None,
        template_type: str | None = None,
        created_at: datetime | None = None,
        content: str | None = None,
        archived: bool = False,
        hidden: bool = False,
        service_id: UUID4 | None = None,
        process_type: str | None = None,
        created_by_id: UUID4 | None = None,
        version: int = 0,
    ) -> Row[Any]:
        id = id or uuid4()
        legacy_templates = metadata_legacy.tables['templates']
        legacy_templates_hist = metadata_legacy.tables['templates_history']
        legacy_process_type = metadata_legacy.tables['template_process_type']
        data = {
            'id': id,
            'name': name or f'sample-template-{id}',
            'template_type': template_type or NotificationType.SMS,
            'created_at': created_at or datetime.now(timezone.utc),
            'content': content or f'sample-content{id}',
            'archived': archived,
            'hidden': hidden,
            'service_id': service_id,
            'process_type': process_type,
            'created_by_id': created_by_id,
            'version': version,
        }

        session = session or no_commit_session

        if service_id is None:
            service = await sample_service(session, uuid4())
            data['service_id'] = service.id
        else:
            legacy_services = metadata_legacy.tables['services']
            select_service_stmt = select(legacy_services).where(legacy_services.c.id == service_id)
            service = (await session.execute(select_service_stmt)).one()

        data['created_by_id'] = created_by_id or service.created_by_id
        select_process_stmt = select(legacy_process_type).where(
            legacy_process_type.c.name == (process_type or 'normal')
        )
        data['process_type'] = (await session.execute(select_process_stmt)).one().name

        # Insert without commit
        insert_template_stmt = insert(legacy_templates).values(**data)
        await session.execute(insert_template_stmt)
        insert_template_hist_stmt = insert(legacy_templates_hist).values(**data)
        await session.execute(insert_template_hist_stmt)

        # Get the new object
        select_stmt = select(legacy_templates).where(legacy_templates.c.id == id)
        template = (await session.execute(select_stmt)).one()
        return template

    return _wrapper


@pytest.fixture
def sample_service_sms_sender(
    no_commit_session: AsyncSession,
) -> Callable[..., Awaitable[Row[Any]]]:
    """Generates a sample ServiceSmsSender - Does not commit to the database.

    Args:
        no_commit_session (AsyncSession): A non-commit test session

    Returns:
        Callable[..., Awaitable[Row[Any]]]: The function to create an ServiceSmsSender
    """

    async def _wrapper(
        service_id: UUID4,
        session: AsyncSession | None = None,
        archived: bool = False,
        created_at: datetime | None = None,
        id: UUID4 | None = None,
        is_default: bool = True,
        sms_sender: str | None = None,
    ) -> Row[Any]:
        id = id or uuid4()
        session = session or no_commit_session
        legacy_service_sms_senders = metadata_legacy.tables['service_sms_senders']

        # No need for the values to be in a separate dictionary because they have all the data already
        insert_stmt = insert(legacy_service_sms_senders).values(
            service_id=service_id,
            archived=archived,
            created_at=created_at or datetime.now(timezone.utc),
            id=id,
            is_default=is_default,
            sms_sender=sms_sender or f'+1{randint(100000000, 999999999)}',
        )
        await session.execute(insert_stmt)
        select_stmt = select(legacy_service_sms_senders).where(legacy_service_sms_senders.c.id == id)
        return (await session.execute(select_stmt)).one()

    return _wrapper
