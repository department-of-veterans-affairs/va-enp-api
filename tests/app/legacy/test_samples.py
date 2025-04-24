"""Test any implemented samples."""

from typing import Any, Awaitable, Callable

from sqlalchemy import Row


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
    sample_service: Callable[..., Awaitable[Row[Any]]],
) -> None:
    """Call the sample_api_key generator.

    Args:
        sample_api_key (Callable[..., Awaitable[Row[Any]]]): An API Key object as a an SQLAlchemy Row
        sample_service (Callable[..., Awaitable[Row[Any]]]): A Service object as a an SQLAlchemy Row
    """
    await sample_api_key()
    # Test branching logic used for created_by_id
    await sample_api_key(service_id=(await sample_service()).id)
    await sample_api_key(created_by_id=(await sample_service()).created_by_id)
