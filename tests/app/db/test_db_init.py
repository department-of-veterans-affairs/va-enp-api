"""Test module for testing the app/db/db_init.py file."""

import logging

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.db.db_init import (
    get_db_session,
    get_read_session_with_context,
    get_read_session_with_depends,
    get_write_session_with_context,
    get_write_session_with_depends,
)

READ_QUERY = text("SELECT 'Hello world!'")
WRITE_QUERY = text('CREATE TABLE foo (id INT); DROP TABLE foo;')


def test_init_db() -> None:
    """Ensure init_db creates the read and write async database engines.

    The autouse fixture tests/app/conftest.py::test_init_db calls app/db/db_init.py
    to assign values to the module variables _engine_napi_read and _engine_napi_write.
    Ensure that those values are of type AsyncEngine.
    """
    from app.db.db_init import _engine_napi_read, _engine_napi_write

    assert isinstance(_engine_napi_read, AsyncEngine)
    assert isinstance(_engine_napi_write, AsyncEngine)


@pytest.mark.parametrize('hide_parameters', [True, False])
def test_create_engines_hide_parameters(monkeypatch: pytest.MonkeyPatch, hide_parameters: bool) -> None:
    """Ensure create_engines forwards SQLALCHEMY_HIDE_PARAMETERS-derived options.

    Note: this only checks that create_async_engine receives the hide_parameters kwarg; it does not validate log output.
    """
    from app.db import db_init

    # Preserve module globals so we can restore them after stubbing engine creation.
    original_read = db_init._engine_napi_read
    original_write = db_init._engine_napi_write

    # Collect kwargs passed to create_async_engine for assertions.
    created_kwargs: list[dict[str, object]] = []

    def fake_create_async_engine(*_args: object, **kwargs: object) -> object:
        created_kwargs.append(kwargs)
        return object()

    # Replace engine factory and options to avoid real DB connections.
    monkeypatch.setattr(db_init, 'create_async_engine', fake_create_async_engine)
    monkeypatch.setattr(db_init, 'SQLALCHEMY_ENGINE_OPTIONS', {'hide_parameters': hide_parameters})

    try:
        db_init.create_engines(pool_pre_ping=False)

        assert len(created_kwargs) == 2

        # Both read/write engine creations should receive the same hide_parameters value.
        assert [kwargs['hide_parameters'] for kwargs in created_kwargs] == [
            hide_parameters,
            hide_parameters,
        ]

    finally:
        # Always restore module globals, even if assertions fail, to avoid test bleed.
        db_init._engine_napi_read = original_read
        db_init._engine_napi_write = original_write


@pytest.mark.parametrize('hide_parameters', [True, False])
def test_hide_parameters_redacts_engine_logs(caplog: pytest.LogCaptureFixture, hide_parameters: bool) -> None:
    """Verify engine logs include or redact bound values based on hide_parameters."""
    engine = create_engine('sqlite://', echo=True, hide_parameters=hide_parameters)
    try:
        caplog.clear()
        with caplog.at_level(logging.INFO, logger='sqlalchemy.engine'):
            with pytest.raises(SQLAlchemyError):
                with engine.connect() as conn:
                    conn.execute(text('SELECT * FROM missing_table WHERE id = :value'), {'value': 'example-value'})

        messages = [record.getMessage() for record in caplog.records]
        assert any('missing_table' in message for message in messages)

        if hide_parameters:
            assert all('example-value' not in message for message in messages)
        else:
            assert any('example-value' in message for message in messages)
    finally:
        engine.dispose()


@pytest.mark.parametrize('engine_type', ['read', 'write'])
def test_get_db_session_none(engine_type: str) -> None:
    """Ensure globals are populated before calling get_db_session."""
    with pytest.raises(ValueError, match=f'The db {engine_type} engine has not been initialized. None type received.'):
        get_db_session(None, engine_type)


async def test_no_commit_session(no_commit_session: AsyncSession) -> None:
    """Ensure the session fixture can be used as a session."""
    await no_commit_session.execute(READ_QUERY)


async def test_get_db_session_write() -> None:
    """The write database engine should be able to execute write queries.

    There is no test for the read engine because the local setup only includes one database user,
    which is the same user as for the write engine.  The connection URI is the same.
    """
    from app.db.db_init import _engine_napi_write

    session_maker = get_db_session(_engine_napi_write, 'write')

    async with session_maker() as session:
        # This query should not raise an exception.
        await session.execute(WRITE_QUERY)
        await session.commit()


class TestReadWriteSessions:
    """Test the read and write session functions."""

    async def test_get_read_session(self) -> None:
        """Test the get_read_session function."""
        async for session in get_read_session_with_depends():
            await session.execute(READ_QUERY)

    async def test_get_read_session_with_context(self) -> None:
        """Test the get_read_session_with_context function."""
        async with get_read_session_with_context() as session:
            await session.execute(READ_QUERY)

    async def test_get_write_session(self) -> None:
        """Test the get_write_session function."""
        async for session in get_write_session_with_depends():
            await session.execute(WRITE_QUERY)

    async def test_get_write_session_with_context(self) -> None:
        """Test the get_write_session_with_context function."""
        async with get_write_session_with_context() as session:
            await session.execute(WRITE_QUERY)
