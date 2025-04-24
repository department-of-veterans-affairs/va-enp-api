"""Pytest setup for all legacy code."""

from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Awaitable, Callable
from uuid import uuid4

import pytest
from pydantic import UUID4
from sqlalchemy import Row, delete

from app.db.db_init import get_write_session_with_context, metadata_legacy
from app.legacy.dao.api_key_dao import LegacyApiKeyDao
from app.legacy.dao.services_dao import LegacyServiceDao
from app.legacy.dao.users_dao import LegacyUserDao


@pytest.fixture
async def sample_user() -> AsyncGenerator[Callable[..., Awaitable[Row[Any]]], None]:
    """Creates a User in the database and cleans up when the fixture is torn down.

    Yields:
        AsyncGenerator[Callable[..., Awaitable[Row[Any]]], None]: The function to create a User
    """
    user_ids = []

    async def _wrapper(
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
        user = await LegacyUserDao.create_user(
            id=id,
            name=name or f'sample-user-{id}',
            email_address=email_address or f'create-user-{id}@va.gov',
            created_at=created_at or datetime.now(timezone.utc),
            failed_login_count=failed_login_count,
            state=state,
            platform_admin=platform_admin,
            blocked=blocked,
        )
        user_ids.append(id)
        return user

    yield _wrapper

    # Teardown
    await user_cleanup(user_ids)


@pytest.fixture
async def sample_service(
    sample_user: Callable[..., Awaitable[Row[Any]]],
) -> AsyncGenerator[Callable[..., Awaitable[Row[Any]]], None]:
    """Generate a sample Service.

    Args:
        sample_user (Callable[..., Awaitable[Row[Any]]]): Generates sample Users

    Yields:
        AsyncGenerator[Callable[..., Awaitable[Row[Any]]], None]: The function to create a Service
    """
    service_ids = []

    async def _wrapper(
        id: UUID4 | None = None,
        name: str | None = None,
        created_at: datetime | None = None,
        active: bool = True,
        message_limit: int = 1000,
        restricted: bool = False,
        research_mode: bool = False,
        created_by_id: UUID4 | None = None,
        prefix_sms: bool = False,
        rate_limit: int = 3000,
        count_as_live: bool = True,
        version: int = 0,
    ) -> Row[Any]:
        id = id or uuid4()
        service = await LegacyServiceDao.create_service(
            id=id,
            name=name or f'sample-service-{id}',
            created_at=created_at or datetime.now(timezone.utc),
            active=active,
            message_limit=message_limit,
            restricted=restricted,
            research_mode=research_mode,
            created_by_id=created_by_id or (await sample_user()).id,
            prefix_sms=prefix_sms,
            rate_limit=rate_limit,
            count_as_live=count_as_live,
            version=version,
        )
        service_ids.append(id)
        return service

    yield _wrapper

    # Teardown
    await service_cleanup(service_ids)


@pytest.fixture
async def sample_api_key(
    sample_service: Callable[..., Awaitable[Row[Any]]],
) -> AsyncGenerator[Callable[..., Awaitable[Row[Any]]], None]:
    """Generate a sample API Key.

    Args:
        sample_service (Callable[..., Awaitable[Row[Any]]]): Generates sample Service

    Yields:
        AsyncGenerator[Callable[..., Awaitable[Row[Any]]], None]: The function to create an API Key
    """
    api_key_ids = []

    async def _wrapper(
        id: UUID4 | None = None,
        name: str | None = None,
        secret: str | None = None,
        service_id: UUID4 | None = None,
        key_type: str | None = None,
        revoked: bool = False,
        created_at: datetime | None = None,
        created_by_id: UUID4 | None = None,
        version: int = 0,
    ) -> Row[Any]:
        id = id or uuid4()
        if created_by_id is None:
            if service_id is not None:
                # Look it up if one exists
                created_by_id = (await LegacyServiceDao.get_service(service_id)).created_by_id
            else:
                service = await sample_service()
                service_id = service.id
                created_by_id = service.created_by_id

        api_key = await LegacyApiKeyDao.create_api_key(
            id=id,
            name=name or f'sample-api-key-{id}',
            secret=secret or f'secret-{uuid4()}',
            service_id=service_id or (await sample_service()).id,
            key_type=key_type or LegacyApiKeyDao.NORMAL_TYPE,
            revoked=revoked,
            created_at=created_at or datetime.now(timezone.utc),
            created_by_id=created_by_id,
            version=version,
        )
        api_key_ids.append(id)
        return api_key

    yield _wrapper

    # Teardown
    await api_key_cleanup(api_key_ids)


async def user_cleanup(user_ids: list[UUID4]) -> None:
    """Cleanup created Users.

    Args:
        user_ids (list[UUID4]): List of User ids
    """
    legacy_users = metadata_legacy.tables['users']
    async with get_write_session_with_context() as session:
        for user_id in user_ids:
            await session.execute(delete(legacy_users).where(legacy_users.c.id == user_id))
        await session.commit()


async def service_cleanup(service_ids: list[UUID4]) -> None:
    """Cleanup created Services.

    Args:
        service_ids (list[UUID4]): List of Service ids
    """
    legacy_services = metadata_legacy.tables['services']
    async with get_write_session_with_context() as session:
        for service_id in service_ids:
            await session.execute(delete(legacy_services).where(legacy_services.c.id == service_id))
        await session.commit()


async def api_key_cleanup(api_key_ids: list[UUID4]) -> None:
    """Cleanup created API Keys.

    Args:
        api_key_ids (list[UUID4]): List of api_key ids
    """
    legacy_api_keys = metadata_legacy.tables['api_keys']
    async with get_write_session_with_context() as session:
        for api_key_id in api_key_ids:
            await session.execute(delete(legacy_api_keys).where(legacy_api_keys.c.id == api_key_id))
        await session.commit()
