"""Fixtures and setup to test the app."""

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.db_init import close_db, get_db_session, init_db


@pytest_asyncio.fixture(loop_scope='session', scope='session', autouse=True)
async def test_init_db() -> AsyncGenerator[None, None]:
    """At the start of testing, create async engines for read-only and read-write database access.

    Dispose of the engines when testing concludes.  These actions resemble the "lifespan" steps
    in main.py.

    The database server should be running and accepting connections.
    """
    await init_db(True)
    yield
    await close_db()


@pytest.fixture
async def test_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a transactional, read-write database session.

    Tests that use this fixture should not need to worry about rolling back database changes.
    """
    # _engine_napi_write will always be None if imported at the top.
    from app.db.db_init import _engine_napi_write

    assert _engine_napi_write is not None, 'This should have been initialized by the test_init_db fixture.'

    async with _engine_napi_write.connect() as connection:
        # Begin a transaction.
        async with connection.begin():
            session_maker = get_db_session(_engine_napi_write, 'write')
            async with session_maker() as session:
                yield session
        # A rollback should occur automatically because the "begin" block doesn't manually commit.
