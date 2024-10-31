"""Test module for testing the app/db/db_init.py file."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, async_scoped_session

# from app.db import DB_READ_URI, DB_WRITE_URI
from app.db.db_init import (
    close_db,
    get_db_session,
    get_read_session,
    get_read_session_with_context,
    get_write_session,
    get_write_session_with_context,
    init_db,
)


@patch('app.db.db_init.create_async_engine')
@pytest.mark.asyncio
@pytest.mark.parametrize(
    'read_uri_value',
    [
        'read_uri',
        '',
    ],
    ids=(
        'with_read_uri',
        'without_read_uri',
    ),
)
async def test_init_db(mock_create_async_engine: Mock, read_uri_value: str) -> None:
    """Test the init_db function."""
    patch('app.db.db_init.DB_READ_URI', return_value=read_uri_value)
    # patch('app.db.db_init.DB_WRITE_URI', return_value='write_uri')
    # patch.dict(os.environ, {'DB_READ_URI': '', 'app.db.DB_WRITE_URI': 'write_uri'}, clear=True)

    # mock_create_async_engine = patch('app.db.db_init.create_async_engine')
    # mock_conn = Mock()
    # mock_create_async_engine.return_value.begin.return_value = Mock()

    await init_db()

    assert mock_create_async_engine.call_count == 2 if read_uri_value else 1
    # assert mock_conn.run_sync.call_count == 2 if DB_READ_URI else 1


@patch('app.db.db_init.engine_write', spec=AsyncMock)
@patch('app.db.db_init.engine_read', spec=AsyncMock)
@pytest.mark.asyncio
async def test_close_db(mock_engine_read: AsyncMock, mock_engine_write: AsyncMock) -> None:
    """Test the close_db function to ensure db engines are closed when called."""
    mock_engine_read.dispose = AsyncMock()
    mock_engine_write.dispose = AsyncMock()

    await close_db()

    mock_engine_read.dispose.assert_called_once()
    mock_engine_write.dispose.assert_called_once()


def test_get_db_session_success() -> None:
    """Test the get_db_session function returns the expected values."""
    mock_engine = Mock(spec=AsyncEngine)
    session_maker = get_db_session(mock_engine, 'test')

    assert session_maker.kw['bind'] == mock_engine
    assert not session_maker.kw['expire_on_commit']


def test_get_db_session_failure() -> None:
    """Test the get_db_session function raises a ValueError when the db engine is None."""
    with pytest.raises(ValueError, match='The db test engine has not been initialized. None type received.'):
        get_db_session(None, 'test')


@patch('app.db.db_init.async_scoped_session', return_value=Mock(spec=async_scoped_session))
@patch('app.db.db_init.engine_read', Mock(spec=AsyncEngine))
@patch('app.db.db_init.engine_write', Mock(spec=AsyncEngine))
class TestReadWriteSessions:
    """Test the read and write session functions."""

    @pytest.mark.asyncio
    async def test_get_read_session(self, mock_session: Mock) -> None:
        """Test the get_read_session function."""
        async for _session in get_read_session():
            ...

        mock_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_read_session_with_context(self, mock_session: Mock) -> None:
        """Test the get_read_session_with_context function."""
        async with get_read_session_with_context():
            ...

        mock_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_write_session(self, mock_session: Mock) -> None:
        """Test the get_write_session function."""
        async for _session in get_write_session():
            ...

        mock_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_write_session_with_context(self, mock_session: Mock) -> None:
        """Test the get_write_session_with_context function."""
        async with get_write_session_with_context():
            ...

        mock_session.assert_called_once()


@patch('app.db.db_init.engine_write', None)
@patch('app.db.db_init.engine_read', None)
class TestReadWriteSessionsFailure:
    """Test the read and write session functions."""

    @pytest.mark.asyncio
    async def test_get_read_session_failure(self) -> None:
        """Test the get_read_session function raises a ValueError when the db engine is None."""
        with pytest.raises(ValueError, match='The db read engine has not been initialized. None type received.'):  # noqa: PT012
            async for _session in get_read_session():
                ...

    @pytest.mark.asyncio
    async def test_get_read_session_with_context_failure(self) -> None:
        """Test the get_read_session_with_context function raises a ValueError when the db engine is None."""
        with pytest.raises(ValueError, match='The db read engine has not been initialized. None type received.'):
            async with get_read_session_with_context():
                ...

    @pytest.mark.asyncio
    async def test_get_write_session_failure(self) -> None:
        """Test the get_write_session function raises a ValueError when the db engine is None."""
        with pytest.raises(ValueError, match='The db write engine has not been initialized. None type received.'):  # noqa: PT012
            async for _session in get_write_session():
                ...

    @pytest.mark.asyncio
    async def test_get_write_session_with_context_failure(self) -> None:
        """Test the get_write_session_with_context function raises a ValueError when the db engine is None."""
        with pytest.raises(ValueError, match='The db write engine has not been initialized. None type received.'):
            async with get_write_session_with_context():
                ...
