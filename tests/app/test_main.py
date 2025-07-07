"""Test suite for initializing FastAPI application."""

from asyncio import CancelledError
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from starlette import status

from app.clients.redis_client import RedisClientManager
from app.main import CustomFastAPI, lifespan, safe_cleanup
from tests.conftest import ENPTestClient


def test_simple_route(client: ENPTestClient) -> None:
    """Test GET /enp to return Hello World.

    Args:
        client (ENPTestClient): Custom FastAPI client fixture

    """
    resp = client.get('/enp')
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == {'Hello': 'World'}
    assert 'X-Request-ID' in resp.headers


@patch('app.main.logger')
def test_simple_route_logs_hello_world(mock_logger: Mock, client: ENPTestClient) -> None:
    """Test that GET /enp logs 'Hello World' as an info log.

    Args:
        mock_logger (Mock): Mocked logger for capturing log calls.
        client (ENPTestClient): Custom FastAPI client fixture

    """
    client.get('/enp')
    mock_logger.info.assert_called_with('Hello World')


def test_specified_request_id_is_preserved(client: ENPTestClient) -> None:
    """Test that GET /enp headers propagate x-request-id from request to response.

    Args:
        client (ENPTestClient): Custom FastAPI client fixture

    """
    request_id = uuid4().hex
    response = client.get('/enp', headers={'X-Request-ID': request_id})
    # Ensure context data is available in the response
    assert 'X-Request-ID' in response.headers
    assert response.headers['X-Request-ID'] == request_id


async def test_lifespan_normal() -> None:
    """Test normal lifespan execution.

    Test that init_db() is called during stratup.
    Test that close_db() is called after normal context exit.

    """
    # Create mock Redis client with a no-op ping
    mock_redis_client = Mock()
    mock_redis_client.ping = AsyncMock(return_value=True)

    with (
        patch.object(RedisClientManager, 'get_client', return_value=mock_redis_client),
        patch('app.main.init_db', new_callable=AsyncMock) as mock_init_db,
        patch('app.main.close_db', new_callable=AsyncMock) as mock_close_db,
    ):
        app = CustomFastAPI(lifespan=lifespan)

        async with lifespan(app):
            pass

        mock_init_db.assert_awaited_once()
        mock_close_db.assert_awaited_once()


async def test_lifespan_cancelled_exception() -> None:
    """Test lifespan execution when asyncio.CancelledError raised.

    Raises:
        CancelledError: Raised during shutdown, uvicorn ctrl-c

    Test that init_db() is called during stratup.
    Test that close_db() is called when asyncio.CancelledError raised in lifespan.

    """
    # Create mock Redis client with a no-op ping
    mock_redis_client = Mock()
    mock_redis_client.ping = AsyncMock(return_value=True)

    with (
        patch.object(RedisClientManager, 'get_client', return_value=mock_redis_client),
        patch('app.main.init_db', new_callable=AsyncMock) as mock_init_db,
        patch('app.main.close_db', new_callable=AsyncMock) as mock_close_db,
    ):
        app = CustomFastAPI(lifespan=lifespan)

        # We expect an asyncio.CancelledError to be gracefully caught
        # Cannot test KeyboardInterrupt because it stops pytest. Hooks do not play nice with asyncio's CancelledError
        async with lifespan(app):
            raise CancelledError()

        mock_init_db.assert_awaited_once()
        mock_close_db.assert_awaited_once()


async def test_lifespan_finally_block_cleanup() -> None:
    """Test that all cleanup operations in the finally block are executed.

    This test verifies that the finally block properly calls:
    - safe_cleanup for providers
    - safe_cleanup for database
    - safe_cleanup for Redis
    - final logger.info statement

    """
    # Create mock Redis client and manager
    mock_redis_client = Mock()
    mock_redis_client.ping = AsyncMock(return_value=True)
    mock_redis_manager = Mock()
    mock_redis_manager.get_client.return_value = mock_redis_client
    mock_redis_manager.close = AsyncMock()

    with (
        patch('app.main.RedisClientManager', return_value=mock_redis_manager),
        patch('app.main.init_db', new_callable=AsyncMock) as mock_init_db,
        patch('app.main.close_db', new_callable=AsyncMock) as mock_close_db,
        patch('app.main.safe_cleanup', new_callable=AsyncMock) as mock_safe_cleanup,
        patch('app.main.logger') as mock_logger,
    ):
        app = CustomFastAPI(lifespan=lifespan)

        # Test normal exit path
        async with lifespan(app):
            pass

        # Verify initialization happened
        mock_init_db.assert_awaited_once()

        # Verify all safe_cleanup calls were made with correct arguments
        from typing import Any, Callable

        expected_cleanup_calls: list[tuple[Callable[[], Any], str]] = [
            # Providers cleanup
            (app.enp_state.clear_providers, 'Providers'),
            # Database cleanup
            (mock_close_db, 'Database'),
            # Redis cleanup
            (mock_redis_manager.close, 'Redis'),
        ]

        assert mock_safe_cleanup.await_count == 3

        # Check each safe_cleanup call
        for i, (expected_func, expected_name) in enumerate(expected_cleanup_calls):
            call_args = mock_safe_cleanup.await_args_list[i]
            # For the providers cleanup, we can't directly compare lambdas,
            # so we check the resource name instead
            if expected_name == 'Providers':
                assert call_args[0][1] == expected_name
            else:
                assert call_args[0][0] == expected_func
                assert call_args[0][1] == expected_name

        # Verify final logger statement
        mock_logger.info.assert_called_with('AsyncContextManager lifespan shutdown complete')


async def test_lifespan_finally_block_cleanup_with_exception() -> None:
    """Test that cleanup operations in finally block execute even when an exception occurs.

    This ensures that all resources are properly cleaned up regardless of whether
    the lifespan context exits normally or with an exception.

    Raises:
        CancelledError: Raised during test to simulate shutdown scenario.

    """
    # Create mock Redis client and manager
    mock_redis_client = Mock()
    mock_redis_client.ping = AsyncMock(return_value=True)
    mock_redis_manager = Mock()
    mock_redis_manager.get_client.return_value = mock_redis_client
    mock_redis_manager.close = AsyncMock()

    with (
        patch('app.main.RedisClientManager', return_value=mock_redis_manager),
        patch('app.main.init_db', new_callable=AsyncMock) as mock_init_db,
        patch('app.main.close_db', new_callable=AsyncMock),
        patch('app.main.safe_cleanup', new_callable=AsyncMock) as mock_safe_cleanup,
        patch('app.main.logger') as mock_logger,
    ):
        app = CustomFastAPI(lifespan=lifespan)

        # Test exception path with CancelledError
        async with lifespan(app):
            raise CancelledError()

        # Verify initialization happened
        mock_init_db.assert_awaited_once()

        # Verify all safe_cleanup calls were made even with exception
        assert mock_safe_cleanup.await_count == 3

        # Verify final logger statement was called even with exception
        mock_logger.info.assert_called_with('AsyncContextManager lifespan shutdown complete')


async def test_safe_cleanup_function() -> None:
    """Test the safe_cleanup function handles both sync and async cleanup functions.

    This test verifies that safe_cleanup:
    - Properly handles sync cleanup functions
    - Properly handles async cleanup functions
    - Logs success messages
    - Logs and handles exceptions gracefully

    """
    with patch('app.main.logger') as mock_logger:
        # Test sync cleanup function
        sync_cleanup = Mock()
        await safe_cleanup(sync_cleanup, 'TestResource')

        sync_cleanup.assert_called_once()
        mock_logger.info.assert_called_with('TestResource cleanup completed')

        # Reset mock
        mock_logger.reset_mock()

        # Test async cleanup function
        async_cleanup = AsyncMock()
        await safe_cleanup(async_cleanup, 'AsyncTestResource')

        async_cleanup.assert_awaited_once()
        mock_logger.info.assert_called_with('AsyncTestResource cleanup completed')

        # Reset mock
        mock_logger.reset_mock()

        # Test cleanup function that raises exception
        failing_cleanup = Mock(side_effect=Exception('Cleanup failed'))
        await safe_cleanup(failing_cleanup, 'FailingResource')

        failing_cleanup.assert_called_once()
        mock_logger.exception.assert_called_with('FailingResource cleanup failed: Cleanup failed')


# Import safe_cleanup for testing
