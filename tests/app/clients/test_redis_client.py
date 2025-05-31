"""RedisClientManager tests."""

from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from redis.asyncio import Redis
from redis.exceptions import ConnectionError, RedisError, TimeoutError

from app.clients.redis_client import _MAX_REDIS_RETRIES, RedisClientManager
from app.exceptions import NonRetryableError, RetryableError


@pytest.fixture
def redis_manager_with_mock() -> RedisClientManager:
    """Fixture that provides a RedisClientManager with an AsyncMock Redis client.

    This fixture sets up a RedisClientManager instance and replaces its internal Redis client
    with a MagicMock that has AsyncMock implementations of the `set`, `get`, `decrby`, and `close` methods,
    making it suitable for use in async unit tests.

    Returns:
        RedisClientManager: An instance with a mocked Redis client ready for testing.
    """
    manager = RedisClientManager(redis_url='redis://localhost')

    # Create a Redis-spec mock and assign async mocks to methods used
    mock_redis = MagicMock(spec=Redis)
    mock_redis.set = AsyncMock()
    mock_redis.get = AsyncMock()
    mock_redis.decrby = AsyncMock()
    mock_redis.close = AsyncMock()

    # Inject into manager
    manager._client = mock_redis
    return manager


class TestRedisClient:
    """Test basic redis client functionality."""

    async def test_close_handles_successful_shutdown(self, redis_manager_with_mock: RedisClientManager) -> None:
        """Ensure Redis client and pool are closed without error."""
        client = redis_manager_with_mock.get_client()
        client.close = AsyncMock()
        with patch.object(redis_manager_with_mock._pool, 'disconnect', new_callable=AsyncMock) as disconnect_mock:
            await redis_manager_with_mock.close()
            client.close.assert_awaited_once()
            disconnect_mock.assert_awaited_once()

    async def test_close_handles_redis_error(self, redis_manager_with_mock: RedisClientManager) -> None:
        """Test that RedisClientManager.close() suppresses RedisError during shutdown."""
        client = redis_manager_with_mock.get_client()
        client.close = AsyncMock(side_effect=RedisError('close failed'))
        with patch.object(redis_manager_with_mock._pool, 'disconnect', new_callable=AsyncMock) as disconnect_mock:
            disconnect_mock.side_effect = RedisError('disconnect failed')
            await redis_manager_with_mock.close()  # Should not raise an error


class TestConsumeRateLimitToken:
    """Test redis client consume_rate_limit_token."""

    async def test_consume_token_allows_when_tokens_available(
        self, redis_manager_with_mock: RedisClientManager
    ) -> None:
        """Test that consume_rate_limit_token returns True when tokens are available."""
        client = cast(AsyncMock, redis_manager_with_mock.get_client())
        client.get.return_value = 3
        client.decrby.return_value = 2

        result = await redis_manager_with_mock.consume_rate_limit_token('test-key', limit=5, window=10)
        assert result is True

    async def test_consume_token_denies_when_tokens_exhausted(
        self, redis_manager_with_mock: RedisClientManager
    ) -> None:
        """Test that consume_rate_limit_token returns False when no tokens are available."""
        client = cast(AsyncMock, redis_manager_with_mock.get_client())
        client.get.return_value = 0

        result = await redis_manager_with_mock.consume_rate_limit_token('test-key', limit=5, window=10)
        assert result is False

    async def test_consume_token_raises_retryable_on_connection_error(
        self, redis_manager_with_mock: RedisClientManager
    ) -> None:
        """Test that a ConnectionError triggers a RetryableError."""
        client = cast(AsyncMock, redis_manager_with_mock.get_client())
        client.set.side_effect = ConnectionError('Redis down')

        with pytest.raises(RetryableError):
            await redis_manager_with_mock.consume_rate_limit_token('test-key', limit=5, window=10)

    async def test_consume_token_raises_retryable_on_timeout(self, redis_manager_with_mock: RedisClientManager) -> None:
        """Test that a TimeoutError triggers a RetryableError."""
        client = cast(AsyncMock, redis_manager_with_mock.get_client())
        client.set.side_effect = TimeoutError('Redis timeout')

        with pytest.raises(RetryableError):
            await redis_manager_with_mock.consume_rate_limit_token('test-key', limit=5, window=10)

    async def test_consume_token_raises_non_retryable_on_redis_error(
        self, redis_manager_with_mock: RedisClientManager
    ) -> None:
        """Test that a RedisError triggers a NonRetryableError."""
        client = cast(AsyncMock, redis_manager_with_mock.get_client())
        client.set.side_effect = RedisError('Unexpected error')

        with pytest.raises(NonRetryableError):
            await redis_manager_with_mock.consume_rate_limit_token('test-key', limit=5, window=10)

    async def test_consume_token_retries_and_reraises_on_retryable_error(
        self, redis_manager_with_mock: RedisClientManager
    ) -> None:
        """Ensure that RetryableError triggers retries and is eventually re-raised after max attempts."""
        client = cast(AsyncMock, redis_manager_with_mock.get_client())
        client.set.side_effect = ConnectionError('transient')

        with patch('app.clients.redis_client.log_on_retry'), pytest.raises(RetryableError):
            await redis_manager_with_mock.consume_rate_limit_token('key', limit=5, window=10)

        assert client.set.call_count == _MAX_REDIS_RETRIES
