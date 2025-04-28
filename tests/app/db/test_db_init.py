"""Test module for testing the app/db/db_init.py file."""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.db.db_init import (
    get_db_session,
    get_read_session_with_context,
    get_read_session_with_depends,
    get_write_session_with_context,
    get_write_session_with_depends,
)

HELLO_WORLD_QUERY = text("SELECT 'Hello world!'")


def test_init_db() -> None:
    """Ensure init_db creates the read and write async database engines.

    The autouse fixture tests/app/conftest.py::test_init_db calls app/db/db_init.py
    to assign values to the module variables _engine_napi_read and _engine_napi_write.
    Ensure that those values are of type AsyncEngine.
    """
    from app.db.db_init import _engine_napi_read, _engine_napi_write

    assert isinstance(_engine_napi_read, AsyncEngine)
    assert isinstance(_engine_napi_write, AsyncEngine)


@pytest.mark.parametrize('engine_type', ['read', 'write'])
def test_get_db_session_none(engine_type: str) -> None:
    """Ensure globals are populated before calling get_db_session."""
    with pytest.raises(ValueError, match=f'The db {engine_type} engine has not been initialized. None type received.'):
        get_db_session(None, engine_type)


async def test_test_db_session(test_db_session: AsyncSession) -> None:
    """Ensure the session fixture can be used as a session."""
    await test_db_session.execute(HELLO_WORLD_QUERY)


async def test_get_db_session_write() -> None:
    """The write database engine should be able to execute write queries.

    There is no test for the read engine because the local setup only includes one database user,
    which is the same user as for the write engine.  The connection URI is the same.
    """
    from app.db.db_init import _engine_napi_write

    session_maker = get_db_session(_engine_napi_write, 'write')

    async with session_maker() as session:
        # This query should not raise an exception.
        await session.execute(HELLO_WORLD_QUERY)


class TestReadWriteSessions:
    """Test the read and write session functions."""

    async def test_get_read_session(self) -> None:
        """Test the get_read_session function."""
        async for session in get_read_session_with_depends():
            await session.execute(text("SELECT 'Hello world!'"))

    async def test_get_read_session_with_context(self) -> None:
        """Test the get_read_session_with_context function."""
        async with get_read_session_with_context() as session:
            await session.execute(text("SELECT 'Hello world!'"))

    async def test_get_write_session(self) -> None:
        """Test the get_write_session function."""
        async for session in get_write_session_with_depends():
            await session.execute(text("SELECT 'Hello world!'"))

    async def test_get_write_session_with_context(self) -> None:
        """Test the get_write_session_with_context function."""
        async with get_write_session_with_context() as session:
            await session.execute(text("SELECT 'Hello world!'"))
