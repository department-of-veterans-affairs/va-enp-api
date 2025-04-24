"""Test module for testing the app/db/db_init.py file."""

from unittest.mock import Mock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, async_scoped_session

from app.db.db_init import (
    close_db,
    get_db_session,
    get_read_session_with_context,
    get_read_session_with_depends,
    get_write_session_with_context,
    get_write_session_with_depends,
)


async def test_close_db() -> None:
    """Test the close_db function to ensure db engines are closed when called."""
    await close_db()


def test_get_db_session_success() -> None:
    """Test the get_db_session function returns the expected values."""
    mock_engine = Mock(spec=AsyncEngine)
    session_maker = get_db_session(mock_engine, 'test')

    assert session_maker.kw['bind'] == mock_engine
    assert not session_maker.kw['expire_on_commit']


def test_get_db_session_failure() -> None:
    """Test the get_db_session function raises a ValueError when the db engine is None."""
    with pytest.raises(ValueError, match=r'The db test engine has not been initialized. None type received.'):
        get_db_session(None, 'test')


@patch('app.db.db_init.async_scoped_session', return_value=Mock(spec=async_scoped_session))
@patch('app.db.db_init._engine_napi_read', Mock(spec=AsyncEngine))
@patch('app.db.db_init._engine_napi_write', Mock(spec=AsyncEngine))
class TestReadWriteSessions:
    """Test the read and write session functions."""

    async def test_get_read_session(self, mock_session: Mock) -> None:
        """Test the get_read_session function."""
        async for _session in get_read_session_with_depends():
            ...

        mock_session.assert_called_once()

    async def test_get_read_session_with_context(self, mock_session: Mock) -> None:
        """Test the get_read_session_with_context function."""
        async with get_read_session_with_context():
            ...

        mock_session.assert_called_once()

    async def test_get_write_session(self, mock_session: Mock) -> None:
        """Test the get_write_session function."""
        async for _session in get_write_session_with_depends():
            ...

        mock_session.assert_called_once()

    async def test_get_write_session_with_context(self, mock_session: Mock) -> None:
        """Test the get_write_session_with_context function."""
        async with get_write_session_with_context():
            ...

        mock_session.assert_called_once()


@patch('app.db.db_init._engine_napi_write', None)
@patch('app.db.db_init._engine_napi_read', None)
class TestReadWriteSessionsFailure:
    """Test the read and write session functions."""

    async def test_get_read_session_failure(self) -> None:
        """Test the get_read_session function raises a ValueError when the db engine is None."""
        with pytest.raises(ValueError, match=r'The db read engine has not been initialized. None type received.'):
            # fmt: off
            async for _session in get_read_session_with_depends(): pass  # noqa: E701
            # fmt: off

    async def test_get_read_session_with_context_failure(self) -> None:
        """Test the get_read_session_with_context function raises a ValueError when the db engine is None."""
        with pytest.raises(ValueError, match=r'The db read engine has not been initialized. None type received.'):
            # fmt: off
            async with get_read_session_with_context(): pass  # noqa: E701
            # fmt: on

    async def test_get_write_session_failure(self) -> None:
        """Test the get_write_session function raises a ValueError when the db engine is None."""
        with pytest.raises(ValueError, match=r'The db write engine has not been initialized. None type received.'):
            # fmt: off
            async for _session in get_write_session_with_depends(): pass  # noqa: E701
            # fmt: on

    async def test_get_write_session_with_context_failure(self) -> None:
        """Test the get_write_session_with_context function raises a ValueError when the db engine is None."""
        with pytest.raises(ValueError, match=r'The db write engine has not been initialized. None type received.'):
            # fmt: off
            async with get_write_session_with_context(): pass  # noqa: E701
            # fmt: on
