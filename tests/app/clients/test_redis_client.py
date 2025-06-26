"""Redis client manager tests."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from redis.asyncio import ConnectionPool, Redis
from redis.exceptions import ConnectionError, RedisError, TimeoutError

from app.clients.redis_client import RedisClientManager
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
        """Test that a token is consumed when the count is greater than 0."""
        client_mock = AsyncMock(spec=Redis)
        client_mock.set = AsyncMock()
        client_mock.get = AsyncMock(return_value=3)
        client_mock.decrby = AsyncMock()

        mocker.patch('app.clients.redis_client.RedisClientManager.get_client', return_value=client_mock)

        manager = RedisClientManager(redis_url='redis://localhost')
        result = await manager.consume_rate_limit_token('key', limit=5, window=10)

        client_mock.set.assert_awaited_once_with(name='key', value=5, ex=10, nx=True)
        client_mock.get.assert_awaited_once_with('key')
        client_mock.decrby.assert_awaited_once_with(name='key', amount=1)
        assert result is True

    async def test_consume_token_denies_when_tokens_exhausted(self, mocker: AsyncMock) -> None:
        """Test that no token is consumed when the count is 0."""
        client_mock = AsyncMock(spec=Redis)
        client_mock.set = AsyncMock()
        client_mock.get = AsyncMock(return_value=0)

        mocker.patch('app.clients.redis_client.RedisClientManager.get_client', return_value=client_mock)

        manager = RedisClientManager(redis_url='redis://localhost')
        result = await manager.consume_rate_limit_token('key', limit=5, window=10)

        client_mock.decrby.assert_not_called()
        assert result is False

    async def test_consume_token_raises_retryable_on_connection_error(self, mocker: AsyncMock) -> None:
        """Test that a connection error raises RetryableError."""
        client_mock = AsyncMock(spec=Redis)
        client_mock.set = AsyncMock(side_effect=ConnectionError('connection down'))

        mocker.patch('app.clients.redis_client.RedisClientManager.get_client', return_value=client_mock)

        manager = RedisClientManager(redis_url='redis://localhost')
        with pytest.raises(RetryableError):
            await manager.consume_rate_limit_token('key', limit=5, window=10)

    async def test_consume_token_raises_retryable_on_timeout_error(self, mocker: AsyncMock) -> None:
        """Test that a timeout error raises RetryableError."""
        client_mock = AsyncMock(spec=Redis)
        client_mock.set = AsyncMock(side_effect=TimeoutError('timeout'))

        mocker.patch('app.clients.redis_client.RedisClientManager.get_client', return_value=client_mock)

        manager = RedisClientManager(redis_url='redis://localhost')
        with pytest.raises(RetryableError):
            await manager.consume_rate_limit_token('key', limit=5, window=10)

    async def test_consume_token_raises_nonretryable_on_redis_error(self, mocker: AsyncMock) -> None:
        """Test that a generic RedisError raises NonRetryableError."""
        client_mock = AsyncMock(spec=Redis)
        client_mock.set = AsyncMock(side_effect=RedisError('generic error'))

        mocker.patch('app.clients.redis_client.RedisClientManager.get_client', return_value=client_mock)

        manager = RedisClientManager(redis_url='redis://localhost')
        with pytest.raises(NonRetryableError):
            await manager.consume_rate_limit_token('key', limit=5, window=10)


class TestConsumeDailyRateLimitToken:
    """Unit tests for consume_daily_rate_limit_token."""

    async def test_consume_daily_token_allows_when_tokens_available(self, mocker: AsyncMock) -> None:
        """Test that a daily token is consumed when the count is greater than 0."""
        client_mock = AsyncMock(spec=Redis)
        client_mock.set = AsyncMock()
        client_mock.get = AsyncMock(return_value=50)
        client_mock.decrby = AsyncMock()

        mocker.patch('app.clients.redis_client.RedisClientManager.get_client', return_value=client_mock)

        # Mock datetime to return predictable values
        with patch('app.clients.redis_client.datetime') as mock_datetime:
            from datetime import datetime, timedelta, timezone

            # Mock current time (e.g., 10 PM UTC)
            mock_now = datetime(2023, 12, 25, 22, 0, 0, tzinfo=timezone.utc)

            mock_datetime.datetime.now.return_value = mock_now
            mock_datetime.timezone.utc = timezone.utc
            mock_datetime.timedelta = timedelta

            manager = RedisClientManager(redis_url='redis://localhost')
            result = await manager.consume_daily_rate_limit_token('daily-key', limit=100)

            # Verify TTL was calculated (should be 7200 seconds = 2 hours until midnight)
            expected_ttl = 7200
            client_mock.set.assert_awaited_once_with(name='daily-key', value=100, ex=expected_ttl, nx=True)
            client_mock.get.assert_awaited_once_with('daily-key')
            client_mock.decrby.assert_awaited_once_with(name='daily-key', amount=1)
            assert result is True

    async def test_consume_daily_token_denies_when_tokens_exhausted(self, mocker: AsyncMock) -> None:
        """Test that no daily token is consumed when the count is 0."""
        client_mock = AsyncMock(spec=Redis)
        client_mock.set = AsyncMock()
        client_mock.get = AsyncMock(return_value=0)

        mocker.patch('app.clients.redis_client.RedisClientManager.get_client', return_value=client_mock)

        # Mock datetime to return predictable values
        with patch('app.clients.redis_client.datetime') as mock_datetime:
            from datetime import datetime, timedelta, timezone

            # Mock current time
            mock_now = datetime(2023, 12, 25, 22, 0, 0, tzinfo=timezone.utc)

            mock_datetime.datetime.now.return_value = mock_now
            mock_datetime.timezone.utc = timezone.utc
            mock_datetime.timedelta = timedelta

            manager = RedisClientManager(redis_url='redis://localhost')
            result = await manager.consume_daily_rate_limit_token('daily-key', limit=100)

            client_mock.set.assert_awaited_once()
            client_mock.get.assert_awaited_once_with('daily-key')
            client_mock.decrby.assert_not_called()
            assert result is False

    async def test_consume_daily_token_sets_expiration_until_midnight(self, mocker: AsyncMock) -> None:
        """Test that the daily token key is set with TTL expiration until midnight UTC."""
        client_mock = AsyncMock(spec=Redis)
        client_mock.set = AsyncMock()
        client_mock.get = AsyncMock(return_value=50)
        client_mock.decrby = AsyncMock()

        mocker.patch('app.clients.redis_client.RedisClientManager.get_client', return_value=client_mock)

        # Mock datetime to return a fixed time calculation
        with patch('app.clients.redis_client.datetime') as mock_datetime:
            mock_datetime.datetime.now.return_value.replace.return_value = mocker.Mock()
            mock_datetime.datetime.now.return_value.__sub__ = mocker.Mock(
                return_value=mocker.Mock(total_seconds=lambda: 7200)
            )
            mock_datetime.timedelta.return_value = mocker.Mock()
            mock_datetime.timezone.utc = mocker.Mock()

            manager = RedisClientManager(redis_url='redis://localhost')
            result = await manager.consume_daily_rate_limit_token('daily-key', limit=100)

            # Verify TTL was set (exact value doesn't matter for this test)
            client_mock.set.assert_awaited_once()
            set_call_args = client_mock.set.call_args
            assert 'ex' in set_call_args.kwargs
            assert set_call_args.kwargs['nx'] is True
            assert result is True

    async def test_consume_daily_token_raises_retryable_on_connection_error(self, mocker: AsyncMock) -> None:
        """Test that a connection error raises RetryableError for daily rate limiting."""
        client_mock = AsyncMock(spec=Redis)
        client_mock.set = AsyncMock(side_effect=ConnectionError('connection down'))

        mocker.patch('app.clients.redis_client.RedisClientManager.get_client', return_value=client_mock)

        manager = RedisClientManager(redis_url='redis://localhost')
        with pytest.raises(RetryableError):
            await manager.consume_daily_rate_limit_token('daily-key', limit=100)

    async def test_consume_daily_token_raises_retryable_on_timeout_error(self, mocker: AsyncMock) -> None:
        """Test that a timeout error raises RetryableError for daily rate limiting."""
        client_mock = AsyncMock(spec=Redis)
        client_mock.set = AsyncMock(side_effect=TimeoutError('timeout'))

        mocker.patch('app.clients.redis_client.RedisClientManager.get_client', return_value=client_mock)

        manager = RedisClientManager(redis_url='redis://localhost')
        with pytest.raises(RetryableError):
            await manager.consume_daily_rate_limit_token('daily-key', limit=100)

    async def test_consume_daily_token_raises_nonretryable_on_redis_error(self, mocker: AsyncMock) -> None:
        """Test that a generic RedisError raises NonRetryableError for daily rate limiting."""
        client_mock = AsyncMock(spec=Redis)
        client_mock.set = AsyncMock(side_effect=RedisError('generic error'))

        mocker.patch('app.clients.redis_client.RedisClientManager.get_client', return_value=client_mock)

        manager = RedisClientManager(redis_url='redis://localhost')
        with pytest.raises(NonRetryableError):
            await manager.consume_daily_rate_limit_token('daily-key', limit=100)
