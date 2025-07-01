"""Redis client manager tests."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from redis.asyncio import ConnectionPool, Redis
from redis.exceptions import ConnectionError, RedisError, TimeoutError

from app.clients.redis_client import RedisClientManager, redis_retry
from app.exceptions import NonRetryableError, RetryableError


class TestRedisClientManager:
    """Test core client management functionality."""

    @patch('app.clients.redis_client.Redis')
    def test_get_client_initializes_client(self, mock_redis: MagicMock) -> None:
        """Test that get_client initializes Redis client if _client is None."""
        manager = RedisClientManager(redis_url='redis://localhost')

        assert manager._client is None

        client = manager.get_client()

        mock_redis.assert_called_once_with(connection_pool=manager._pool)

        assert client is mock_redis.return_value

    @patch('app.clients.redis_client.Redis')
    def test_get_client_reuses_existing_client(self, mock_redis: MagicMock) -> None:
        """Test that get_client reuses existing Redis client."""
        manager = RedisClientManager(redis_url='redis://localhost')

        first_client = manager.get_client()

        second_client = manager.get_client()

        mock_redis.assert_called_once()

        assert first_client is second_client

    async def test_close_success(self) -> None:
        """Test that close shuts down client and pool without error."""
        manager = RedisClientManager(redis_url='redis://localhost')

        mock_client = AsyncMock(spec=Redis)
        mock_pool = AsyncMock(spec=ConnectionPool)

        manager._client = mock_client
        manager._pool = mock_pool

        await manager.close()

        mock_client.aclose.assert_awaited_once()
        mock_pool.disconnect.assert_awaited_once()

    async def test_close_suppresses_redis_error(self) -> None:
        """Test that RedisError during close is logged and suppressed."""
        manager = RedisClientManager(redis_url='redis://localhost')

        mock_client = AsyncMock(spec=Redis)
        mock_pool = AsyncMock(spec=ConnectionPool)
        mock_client.aclose.side_effect = RedisError('mock failure')

        manager._client = mock_client
        manager._pool = mock_pool

        with patch('app.clients.redis_client.logger') as mock_logger:
            await manager.close()

            mock_logger.exception.assert_called_once_with('Redis shutdown failed')


class TestConsumeRateLimitToken:
    """Unit tests for consume_rate_limit_token."""

    async def test_consume_token_allows_when_tokens_available(self, mocker: AsyncMock) -> None:
        """Test that a token is consumed when the count is greater than 0 and verifies operation sequence."""
        client_mock = AsyncMock(spec=Redis)
        client_mock.set = AsyncMock()
        client_mock.get = AsyncMock(return_value=3)
        client_mock.decrby = AsyncMock()

        mocker.patch('app.clients.redis_client.RedisClientManager.get_client', return_value=client_mock)

        manager = RedisClientManager(redis_url='redis://localhost')
        result = await manager.consume_rate_limit_token('test-key', limit=5, window=60)

        # Verify correct sequence and parameters
        client_mock.set.assert_awaited_once_with(name='test-key', value=5, ex=60, nx=True)
        client_mock.get.assert_awaited_once_with('test-key')
        client_mock.decrby.assert_awaited_once_with(name='test-key', amount=1)
        assert result is True

    @pytest.mark.parametrize(
        ('redis_value', 'expected_result'),
        [
            (0, False),  # tokens exhausted
            (None, False),  # key missing
            (-1, False),  # negative value (defensive)
        ],
    )
    async def test_consume_token_denies_when_no_tokens(
        self, redis_value: int | None, expected_result: bool, mocker: AsyncMock
    ) -> None:
        """Test that no token is consumed when tokens are unavailable."""
        client_mock = AsyncMock(spec=Redis)
        client_mock.set = AsyncMock()
        client_mock.get = AsyncMock(return_value=redis_value)

        mocker.patch('app.clients.redis_client.RedisClientManager.get_client', return_value=client_mock)

        manager = RedisClientManager(redis_url='redis://localhost')
        result = await manager.consume_rate_limit_token('key', limit=5, window=10)

        client_mock.decrby.assert_not_called()
        assert result is expected_result

    @pytest.mark.parametrize(
        ('exception_type', 'expected_error'),
        [
            (ConnectionError('connection down'), RetryableError),
            (TimeoutError('timeout'), RetryableError),
            (RedisError('generic error'), NonRetryableError),
        ],
    )
    async def test_consume_token_error_handling(
        self, exception_type: Exception, expected_error: type[Exception], mocker: AsyncMock
    ) -> None:
        """Test error handling for different Redis exception types."""
        client_mock = AsyncMock(spec=Redis)
        client_mock.set = AsyncMock(side_effect=exception_type)

        mocker.patch('app.clients.redis_client.RedisClientManager.get_client', return_value=client_mock)

        manager = RedisClientManager(redis_url='redis://localhost')
        with pytest.raises(expected_error):
            await manager.consume_rate_limit_token('key', limit=5, window=10)

    @pytest.mark.parametrize('operation', ['set', 'get', 'decrby'])
    async def test_error_handling_at_different_stages(self, operation: str, mocker: AsyncMock) -> None:
        """Test error handling when different Redis operations fail."""
        client_mock = AsyncMock(spec=Redis)

        # Set up normal operations
        client_mock.set = AsyncMock()
        client_mock.get = AsyncMock(return_value=3)
        client_mock.decrby = AsyncMock()

        # Make the specified operation fail
        error = ConnectionError('connection failed')
        getattr(client_mock, operation).side_effect = error

        mocker.patch('app.clients.redis_client.RedisClientManager.get_client', return_value=client_mock)

        manager = RedisClientManager(redis_url='redis://localhost')
        with pytest.raises(RetryableError):
            await manager.consume_rate_limit_token('key', limit=5, window=10)


class TestRedisClientManagerConfiguration:
    """Test Redis client configuration and connection handling."""

    def test_connection_pool_configuration(self) -> None:
        """Test that connection pool is configured with correct parameters."""
        with patch('app.clients.redis_client.ConnectionPool') as mock_pool:
            RedisClientManager(redis_url='redis://test:6379/1')

            mock_pool.from_url.assert_called_once_with(
                'redis://test:6379/1',
                decode_responses=True,
                socket_connect_timeout=3,
                socket_timeout=3,
            )

    def test_client_lazy_initialization(self) -> None:
        """Test that Redis client is not created until first use."""
        manager = RedisClientManager(redis_url='redis://localhost')
        assert manager._client is None

        # Client should be created on first access
        client = manager.get_client()
        assert manager._client is not None
        assert client is manager._client


class TestRedisRetryDecorator:
    """Test the Redis retry decorator functionality."""

    async def test_retry_decorator_retries_on_retryable_error(self) -> None:
        """Test that retry decorator retries on RetryableError."""
        retry_count = 0

        @redis_retry()
        async def failing_function() -> bool:
            nonlocal retry_count
            retry_count += 1
            # Add minimal async operation to satisfy async requirements
            await asyncio.sleep(0)
            if retry_count < 3:
                raise RetryableError('Redis temporarily unavailable')
            return True

        # Should succeed after retries
        result = await failing_function()
        assert result is True
        assert retry_count == 3

    async def test_retry_decorator_does_not_retry_non_retryable_error(self) -> None:
        """Test that retry decorator does not retry NonRetryableError."""
        call_count = 0

        @redis_retry()
        async def failing_function() -> bool:
            nonlocal call_count
            call_count += 1
            # Add minimal async operation to satisfy async requirements
            await asyncio.sleep(0)
            raise NonRetryableError('Redis configuration error')

        # Should not retry and raise immediately
        with pytest.raises(NonRetryableError):
            await failing_function()

        assert call_count == 1
