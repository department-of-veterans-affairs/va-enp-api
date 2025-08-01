"""Test any implemented samples."""

from typing import Any, Awaitable, Callable

from sqlalchemy import Row
from sqlalchemy.ext.asyncio import AsyncSession


async def test_sample_user(sample_user: Callable[..., Awaitable[Row[Any]]]) -> None:
    """Call the sample_user generator.

    Args:
        sample_user (Callable[..., Awaitable[Row[Any]]]): A User object as a an SQLAlchemy Row
    """
    await sample_user()


async def test_sample_service(sample_service: Callable[..., Awaitable[Row[Any]]]) -> None:
    """Call the sample_service generator.

    Args:
        sample_service (Callable[..., Awaitable[Row[Any]]]): A Service object as a an SQLAlchemy Row
    """
    await sample_service()


async def test_sample_api_key(
    sample_api_key: Callable[..., Awaitable[Row[Any]]],
) -> None:
    """Call the sample_api_key generator.

    Args:
        sample_api_key (Callable[..., Awaitable[Row[Any]]]): An API Key object as a an SQLAlchemy Row
    """
    await sample_api_key()


async def test_sample_template(
    sample_template: Callable[..., Awaitable[Row[Any]]],
) -> None:
    """Call the sample_template generator.

    Args:
        sample_template (Callable[..., Awaitable[Row[Any]]]): An API Key object as a an SQLAlchemy Row
    """
    await sample_template()


async def test_sample_notification(
    sample_notification: Callable[..., Awaitable[Row[Any]]],
) -> None:
    """Call the sample_notification generator.

    Args:
        sample_notification (Callable[..., Awaitable[Row[Any]]]): A Notifcation  object as a an SQLAlchemy Row
    """
    await sample_notification()


async def test_sample_notification_with_session(
    no_commit_session: AsyncSession,
    sample_api_key: Callable[..., Awaitable[Row[Any]]],
    sample_notification: Callable[..., Awaitable[Row[Any]]],
    sample_service: Callable[..., Awaitable[Row[Any]]],
    sample_template: Callable[..., Awaitable[Row[Any]]],
) -> None:
    """Call the sample_notification generator.

    Args:
        no_commit_session (AsyncSession): A non-commit test session
        sample_api_key (Callable[..., Awaitable[Row[Any]]]): An API Key object as a an SQLAlchemy Row
        sample_notification (Callable[..., Awaitable[Row[Any]]]): A Notifcation  object as a an SQLAlchemy Row
        sample_service (Callable[..., Awaitable[Row[Any]]]): A Service object as a an SQLAlchemy Row
        sample_template (Callable[..., Awaitable[Row[Any]]]): An API Key object as a an SQLAlchemy Row
    """
    async with no_commit_session as session:
        await sample_notification(session)

        # add existing service
        service = await sample_service(session)
        await sample_notification(session=session, service_id=service.id)

        # add existing api_key
        api_key = await sample_api_key(
            session=session,
            service_id=service.id,
        )
        await sample_notification(
            session=session,
            service_id=service.id,
            api_key_id=api_key.id,
        )

        # add existing template
        template = await sample_template(
            session=session,
            service_id=service.id,
        )
        await sample_notification(
            session=session,
            service_id=service.id,
            api_key_id=api_key.id,
            template_id=template.id,
        )


async def test_sample_user_with_session(
    no_commit_session: AsyncSession,
    sample_user: Callable[..., Awaitable[Row[Any]]],
) -> None:
    """Call the sample_user generator.

    Args:
        no_commit_session (AsyncSession): A non-commit test session
        sample_user (Callable[..., Awaitable[Row[Any]]]): A User object as a an SQLAlchemy Row
    """
    async with no_commit_session as session:
        await sample_user(session)


async def test_sample_service_with_session(
    no_commit_session: AsyncSession, sample_service: Callable[..., Awaitable[Row[Any]]]
) -> None:
    """Call the sample_service generator.

    Args:
        no_commit_session (AsyncSession): A non-commit test session
        sample_service (Callable[..., Awaitable[Row[Any]]]): A Service object as a an SQLAlchemy Row
    """
    async with no_commit_session as session:
        await sample_service(session)


async def test_sample_api_key_with_session(
    no_commit_session: AsyncSession,
    sample_api_key: Callable[..., Awaitable[Row[Any]]],
    sample_service: Callable[..., Awaitable[Row[Any]]],
) -> None:
    """Call the sample_api_key generator.

    Args:
        no_commit_session (AsyncSession): A non-commit test session
        sample_api_key (Callable[..., Awaitable[Row[Any]]]): An API Key object as a an SQLAlchemy Row
        sample_service (Callable[..., Awaitable[Row[Any]]]): A Service object as a an SQLAlchemy Row
    """
    async with no_commit_session as session:
        await sample_api_key(session=session, service_id=(await sample_service(session)).id)
        await sample_api_key(session=session, created_by_id=(await sample_service(session)).created_by_id)
        service = await sample_service(session)
        await sample_api_key(
            session=session,
            service_id=service.id,
            created_by_id=service.created_by_id,
        )


async def test_sample_template_with_session(
    no_commit_session: AsyncSession,
    sample_template: Callable[..., Awaitable[Row[Any]]],
    sample_service: Callable[..., Awaitable[Row[Any]]],
) -> None:
    """Call the sample_template generator.

    Args:
        no_commit_session (AsyncSession): A non-commit test session
        sample_template (Callable[..., Awaitable[Row[Any]]]): An API Key object as a an SQLAlchemy Row
        sample_service (Callable[..., Awaitable[Row[Any]]]): A Service object as a an SQLAlchemy Row
    """
    async with no_commit_session as session:
        await sample_template(service_id=(await sample_service(session)).id)
        await sample_template(created_by_id=(await sample_service(session)).created_by_id)
        service = await sample_service(session)
        await sample_template(
            session=session,
            service_id=service.id,
            created_by_id=service.created_by_id,
        )
