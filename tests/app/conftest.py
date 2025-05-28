"""Fixtures and setup to test the app."""

import os
from collections.abc import AsyncGenerator
from typing import Any, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import BackgroundTasks
from moto.server import ThreadedMotoServer
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


@pytest.fixture(scope='session')
def mock_background_task() -> Generator[MagicMock | AsyncMock, Any, None]:
    """Fixture to mock BackgroundTasks.add_task.

    Yields:
        (MagicMock | AsyncMock): A mock object for BackgroundTasks.add_task.
    """
    with patch.object(BackgroundTasks, 'add_task') as mock_task:
        yield mock_task


@pytest.fixture(scope='session')
def moto_server() -> Generator[str, Any, None]:
    """Fixture to run a mocked AWS server for testing.

    See moto docs for more details:
    https://docs.getmoto.org/en/latest/docs/server_mode.html#start-within-python

    Yields:
        str: The endpoint URL of the mocked AWS server.
    """
    # Note: pass `port=0` to get a random free port.
    server = ThreadedMotoServer(port=0)
    server.start()
    host, port = server.get_host_and_port()
    os.environ['AWS_ENDPOINT_URL'] = f'http://{host}:{port}'

    yield f'http://{host}:{port}'

    del os.environ['AWS_ENDPOINT_URL']
    server.stop()
