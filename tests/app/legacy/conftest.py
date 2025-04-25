"""Pytest setup for all legacy code."""

from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Awaitable, Callable
from uuid import uuid4

import pytest
from pydantic import UUID4
from sqlalchemy import Row, delete, insert, select

from app.db.db_init import get_write_session_with_context, metadata_legacy
from app.legacy.dao.services_dao import LegacyServiceDao


@pytest.fixture
async def sample_user(test_db_session) -> AsyncGenerator[Callable[..., Awaitable[Row[Any]]], None]:
    """Creates a User in the database and cleans up when the fixture is torn down.

    Yields:
        AsyncGenerator[Callable[..., Awaitable[Row[Any]]], None]: The function to create a User
    """

    async def _wrapper(
        session=None,
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
        legacy_users = metadata_legacy.tables['users']
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
        select_stmt = select(legacy_users).where(legacy_users.c.id == id)
        if session:
            await session.execute(insert_stmt)
            user = (await session.execute(select_stmt)).one()
        else:
            async with test_db_session as session:
                await session.execute(insert_stmt)
                user = (await session.execute(select_stmt)).one()
        return user

    return _wrapper


@pytest.fixture
async def sample_service(
    test_db_session,
    sample_user: Callable[..., Awaitable[Row[Any]]],
) -> AsyncGenerator[Callable[..., Awaitable[Row[Any]]], None]:
    """Generate a sample Service.

    Args:
        sample_user (Callable[..., Awaitable[Row[Any]]]): Generates sample Users

    Yields:
        AsyncGenerator[Callable[..., Awaitable[Row[Any]]], None]: The function to create a Service
    """

    async def _wrapper(
        session=None,
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
        select_stmt = select(legacy_services).where(legacy_services.c.id == id)

        async def add_user_build_service_stmt():
            if created_by_id is None:
                user = await sample_user(session, uuid4())
                data['created_by_id'] = user.id
            return insert(legacy_services).values(**data)

        if session:
            await session.execute(await add_user_build_service_stmt())
            service = (await session.execute(select_stmt)).one()
        else:
            async with test_db_session as session:
                await session.execute(await add_user_build_service_stmt())
                service = (await session.execute(select_stmt)).one()

        return service

    return _wrapper


@pytest.fixture
async def sample_api_key(
    test_db_session,
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
        session=None,
        id: UUID4 | None = None,
        name: str | None = None,
        secret: str | None = None,
        service_id: UUID4 | None = None,
        key_type: str = 'normal',
        revoked: bool = False,
        created_at: datetime | None = None,
        created_by_id: UUID4 | None = None,
        version: int = 0,
    ) -> Row[Any]:
        id = id or uuid4()
        # if created_by_id is None:
        #     if service_id is not None:
        #         # Look it up if one exists
        #         created_by_id = (await LegacyServiceDao.get_service(service_id)).created_by_id
        #     else:
        #         service = await sample_service()
        #         service_id = service.id
        #         created_by_id = service.created_by_id

        # api_key = await LegacyApiKeyDao.create_api_key(
        #     id=id,
        #     name=name or f'sample-api-key-{id}',
        #     secret=secret or f'secret-{uuid4()}',
        #     service_id=service_id or (await sample_service()).id,
        #     key_type=key_type or LegacyApiKeyDao.NORMAL_TYPE,
        #     revoked=revoked,
        #     created_at=created_at or datetime.now(timezone.utc),
        #     created_by_id=created_by_id,
        #     version=version,
        # )
        # api_key_ids.append(id)
        # return api_key
        legacy_api_keys = metadata_legacy.tables['api_keys']
        data = {
            'id': id,
            'name': name or f'sample-api-key-{id}',
            'secret': secret or f'secret-{uuid4()}',
            'service_id': service_id or (await sample_service()).id,
            'key_type': key_type,
            'revoked': revoked,
            'created_at': created_at or datetime.now(timezone.utc),
            'created_by_id': created_by_id,
            'version': version,
        }

        async def add_user_service_build_key_stmt():
            if created_by_id is None:
                service = await sample_service(session, uuid4())
                data['created_by_id'] = service.created_by_id
            return insert(legacy_api_keys).values(**data)

        select_stmt = select(legacy_api_keys).where(legacy_api_keys.c.id == id)
        if session:
            await session.execute(await add_user_service_build_key_stmt())
            service = (await session.execute(select_stmt)).one()
        else:
            async with test_db_session as session:
                await session.execute(await add_user_service_build_key_stmt())
                service = (await session.execute(select_stmt)).one()
        return service
        # async with test_db_session as session:
        #     if created_by_id is None:
        #         if service_id is not None:
        #             # Look it up if one exists

        #             created_by_id = (await LegacyServiceDao.get_service(service_id)).created_by_id
        #         else:
        #             service = await sample_service()
        #             service_id = service.id
        #             created_by_id = service.created_by_id

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
