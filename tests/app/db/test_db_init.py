"""Test module for testing the app/db/db_init.py file."""

from collections.abc import AsyncIterator, Callable
from typing import AsyncContextManager

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_scoped_session
from sqlalchemy.sql.elements import TextClause

from app.db.db_init import (
    get_db_session,
    get_read_session_with_context,
    get_read_session_with_depends,
    get_write_session_with_context,
    get_write_session_with_depends,
)

TABLES_QUERY = text("SELECT table_name FROM information_schema.tables WHERE table_schema='public';")

# The branding_type table, and the associated cascades, should not affect tables
# relevant to routes in use.
TRUNCATE_QUERY = text('TRUNCATE branding_type CASCADE;')


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


@pytest.mark.parametrize('engine', ['_engine_napi_read', '_engine_napi_write'])
@pytest.mark.asyncio
async def test_get_db_session_read(engine: str) -> None:
    """The read and write database engines both should be able to execute read queries."""
    imports = __import__('app.db.db_init', fromlist=[engine])
    session_maker = get_db_session(getattr(imports, engine), 'read')

    async with session_maker() as session:
        result = await session.execute(TABLES_QUERY)

    tables = result.scalars().all()
    assert 'notifications' in tables
    assert 'templates' in tables


@pytest.mark.asyncio
async def test_test_db_session(test_db_session: AsyncSession) -> None:
    """Ensure the session fixture works as intended."""
    result = await test_db_session.execute(TABLES_QUERY)
    tables = result.scalars().all()
    assert 'notifications' in tables
    assert 'templates' in tables


@pytest.mark.asyncio
async def test_get_db_session_write() -> None:
    """The write database engine should be able to execute write queries.

    There is no test for the read engine because the local setup only includes one database user,
    which is the same user as for the write engine.  The connection URI is the same.
    """
    from app.db.db_init import _engine_napi_write

    session_maker = get_db_session(_engine_napi_write, 'write')

    async with session_maker() as session:
        # This query should not raise an exception.
        await session.execute(TRUNCATE_QUERY)


@pytest.mark.parametrize('stmt', [TABLES_QUERY, TRUNCATE_QUERY])
@pytest.mark.parametrize(
    'session_generator',
    [
        get_read_session_with_depends,
        get_write_session_with_depends,
    ],
)
@pytest.mark.asyncio
async def test_session_with_depends(
    session_generator: Callable[[], AsyncIterator[async_scoped_session[AsyncSession]]],
    stmt: TextClause,
) -> None:
    """Verify getting a session using the "with_depends" session getters.

    Note that either session can read and write because they use the same database user
    with run locally.
    """
    session_gen = session_generator()

    # As far as I can tell, the type annotations are correct.  MyPy seems confused.
    session: AsyncSession = await anext(session_gen)  # type: ignore

    try:
        # This query should not raise an exception.
        await session.execute(stmt)
    finally:
        # MyPy says that an AsyncGenerator has no method "aclose", but this seems incorrect.
        # Running the test doesn't raise AttributeError.
        await session_gen.aclose()  # type: ignore


@pytest.mark.parametrize('stmt', [TABLES_QUERY, TRUNCATE_QUERY])
@pytest.mark.parametrize(
    'session_context',
    [
        get_read_session_with_context,
        get_write_session_with_context,
    ],
)
@pytest.mark.asyncio
async def test_session_with_context(
    session_context: Callable[[], AsyncContextManager[async_scoped_session[AsyncSession]]],
    stmt: TextClause,
) -> None:
    """Verify getting a session using the "with_context" session getters.

    Note that either session can read and write because they use the same database user with
    run locally.
    """
    async with session_context() as session:
        # This query should not raise an exception.
        await session.execute(stmt)
