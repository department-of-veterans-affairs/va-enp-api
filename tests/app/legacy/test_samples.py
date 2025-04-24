"""Test any implemented samples."""

from typing import Any, Awaitable, Callable

from sqlalchemy import Row


async def test_sample_user(sample_user: Callable[..., Awaitable[Row[Any]]]) -> None:
    """Call the sample_user generator.

    Args:
        sample_user (Callable[..., Awaitable[Row[Any]]]): A User object as a an SQLAlchemy Row
    """
    await sample_user()


async def test_two(sample_service: Callable[..., Awaitable[Row[Any]]]) -> None:
    """Call the sample_service generator.

    Args:
        sample_service (Callable[..., Awaitable[Row[Any]]]): A Service object as a an SQLAlchemy Row
    """
    await sample_service()
