"""Rate limiter tests."""

from typing import Callable, Generator, Tuple
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException, status
from starlette.datastructures import Headers
from starlette.requests import Request as StarletteRequest

from app.clients.redis_client import RedisClientManager
from app.constants import RESPONSE_429
from app.exceptions import NonRetryableError, RetryableError
from app.limits import (
    DailyRateLimiter,
    DailyRateLimitStrategy,
    RateLimiter,
    ServiceRateLimiter,
    ServiceRateLimitStrategy,
)


@pytest.fixture
def mock_context() -> Generator[Tuple[str, str], None, None]:
    """Fixture that mocks the starlette_context context used by ServiceRateLimiter to inject service_id and api_key_id.

    Yields:
        Tuple[str, str]: A tuple containing the mocked service_id and api_key_id (as UUID strings).
    """
    request_id = str(uuid4())
    service_id = str(uuid4())
    api_key_id = str(uuid4())

    with patch('app.limits.context', {'request_id': request_id, 'service_id': service_id, 'api_key_id': api_key_id}):
        yield service_id, api_key_id


@pytest.fixture
def make_request_with_redis() -> Callable[[Mock], StarletteRequest]:
    """Factory fixture that creates a StarletteRequest with a mocked Redis client attached.

    Returns:
        Callable[[Mock], StarletteRequest]: A callable that accepts a mocked Redis client
        and returns a properly configured StarletteRequest.
    """

    def _make(redis_mock: Mock) -> StarletteRequest:
        request = StarletteRequest(
            scope={
                'type': 'http',
                'headers': Headers({}).raw,
                'app': Mock(enp_state=Mock(redis_client_manager=redis_mock)),
            }
        )
        return request

    return _make


class TestServiceRateLimiter:
    """Test the service rate limiter."""

    def test_build_key_format(self) -> None:
        """Test that _build_key generates the correct Redis key format."""
        limiter = ServiceRateLimiter()
        assert limiter._build_key('service-id', 'api-key-id') == 'rate-limit-service-id-api-key-id'

    async def test_allows_request(
        self,
        mock_context: Tuple[str, str],
        make_request_with_redis: Callable[[Mock], StarletteRequest],
    ) -> None:
        """Should allow the request when consume token returns True (token was consumed)."""
        service_id, api_key_id = mock_context
        limiter = ServiceRateLimiter()

        redis_mock = Mock(spec=RedisClientManager)
        redis_mock.consume_rate_limit_token = AsyncMock(return_value=True)

        request = make_request_with_redis(redis_mock)

        await limiter(request)

        redis_mock.consume_rate_limit_token.assert_awaited_once_with(
            f'rate-limit-{service_id}-{api_key_id}',
            limiter.limit,
            limiter.window,
        )

    async def test_blocks_request_when_limit_exceeded(
        self,
        mock_context: Tuple[str, str],
        make_request_with_redis: Callable[[Mock], StarletteRequest],
    ) -> None:
        """Should raise 429 when consume token returns False (limit exceeded)."""
        limiter = ServiceRateLimiter()

        redis_mock = Mock(spec=RedisClientManager)
        redis_mock.consume_rate_limit_token = AsyncMock(return_value=False)

        request = make_request_with_redis(redis_mock)

        with pytest.raises(HTTPException) as exc_info:
            await limiter(request)

        assert exc_info.value.detail == RESPONSE_429
        assert exc_info.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    @pytest.mark.parametrize(
        'raises',
        [
            NonRetryableError('non-retryable failure'),
            RetryableError('temporary failure'),
        ],
    )
    async def test_allows_request_on_errors(
        self,
        mock_context: Tuple[str, str],
        make_request_with_redis: Callable[[Mock], StarletteRequest],
        raises: Exception,
    ) -> None:
        """Should allow the request when consume token throws NonRetryable or RetryableError."""
        service_id, api_key_id = mock_context
        limiter = ServiceRateLimiter()

        redis_mock = Mock(spec=RedisClientManager)
        redis_mock.consume_rate_limit_token = AsyncMock(side_effect=raises)

        request = make_request_with_redis(redis_mock)

        await limiter(request)

        redis_mock.consume_rate_limit_token.assert_awaited_once_with(
            f'rate-limit-{service_id}-{api_key_id}',
            limiter.limit,
            limiter.window,
        )


class TestDailyRateLimiter:
    """Test the daily rate limiter."""

    def test_build_daily_key_format(self) -> None:
        """Test that _build_daily_key generates the correct Redis key format."""
        limiter = DailyRateLimiter()
        assert limiter._build_daily_key('service-id', 'api-key-id') == 'remaining-daily-limit-service-id-api-key-id'

    async def test_allows_request_under_daily_limit(
        self,
        mock_context: Tuple[str, str],
        make_request_with_redis: Callable[[Mock], StarletteRequest],
    ) -> None:
        """Should allow the request when consume daily token returns True (token was consumed)."""
        service_id, api_key_id = mock_context
        limiter = DailyRateLimiter()

        redis_mock = Mock(spec=RedisClientManager)
        redis_mock.consume_daily_rate_limit_token = AsyncMock(return_value=True)

        request = make_request_with_redis(redis_mock)

        await limiter(request)

        redis_mock.consume_daily_rate_limit_token.assert_awaited_once_with(
            f'remaining-daily-limit-{service_id}-{api_key_id}',
            limiter.limit,
        )

    async def test_blocks_request_over_daily_limit(
        self,
        mock_context: Tuple[str, str],
        make_request_with_redis: Callable[[Mock], StarletteRequest],
    ) -> None:
        """Should raise 429 when consume daily token returns False (daily limit exceeded)."""
        limiter = DailyRateLimiter()

        redis_mock = Mock(spec=RedisClientManager)
        redis_mock.consume_daily_rate_limit_token = AsyncMock(return_value=False)

        request = make_request_with_redis(redis_mock)

        with pytest.raises(HTTPException) as exc_info:
            await limiter(request)

        assert exc_info.value.detail == 'Daily rate limit exceeded'
        assert exc_info.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    @pytest.mark.parametrize(
        'raises',
        [
            NonRetryableError('non-retryable failure'),
            RetryableError('temporary failure'),
        ],
    )
    async def test_fails_open_on_redis_errors(
        self,
        mock_context: Tuple[str, str],
        make_request_with_redis: Callable[[Mock], StarletteRequest],
        raises: Exception,
    ) -> None:
        """Should allow the request when consume daily token throws NonRetryable or RetryableError (fail-open)."""
        service_id, api_key_id = mock_context
        limiter = DailyRateLimiter()

        redis_mock = Mock(spec=RedisClientManager)
        redis_mock.consume_daily_rate_limit_token = AsyncMock(side_effect=raises)

        request = make_request_with_redis(redis_mock)

        # Should not raise an exception - fail open
        await limiter(request)

        redis_mock.consume_daily_rate_limit_token.assert_awaited_once_with(
            f'remaining-daily-limit-{service_id}-{api_key_id}',
            limiter.limit,
        )

    def test_limit_initialization_from_env(self) -> None:
        """Test that daily limit is properly initialized from environment variable."""
        with patch('app.limits.os.getenv') as mock_getenv:
            mock_getenv.return_value = '500'
            limiter = DailyRateLimiter()
            assert limiter.limit == 500
            mock_getenv.assert_called_with('DAILY_RATE_LIMIT', 1000)

    def test_limit_initialization_default(self) -> None:
        """Test that daily limit uses default value when environment variable is not set."""
        with patch('app.limits.os.getenv') as mock_getenv:
            mock_getenv.return_value = '1000'  # Simulating default value
            limiter = DailyRateLimiter()
            assert limiter.limit == 1000
            mock_getenv.assert_called_with('DAILY_RATE_LIMIT', 1000)


class TestRateLimiter:
    """Test the RateLimiter class with different strategies."""

    def test_window_property_with_service_strategy(self) -> None:
        """Test that window property returns the correct value for service strategy."""
        strategy = ServiceRateLimitStrategy(limit=10, window=60)
        limiter = RateLimiter(strategy)
        assert limiter.window == 60

    def test_window_property_with_daily_strategy(self) -> None:
        """Test that window property returns None for daily strategy."""
        strategy = DailyRateLimitStrategy(daily_limit=1000)
        limiter = RateLimiter(strategy)
        assert limiter.window is None

    def test_get_key_delegates_to_strategy(self) -> None:
        """Test that get_key delegates to the underlying strategy."""
        # Test with service strategy
        service_strategy = ServiceRateLimitStrategy(limit=5, window=30)
        limiter = RateLimiter(service_strategy)
        key = limiter.get_key('test-service', 'test-api-key')
        assert key == 'rate-limit-test-service-test-api-key'

        # Test with daily strategy
        daily_strategy = DailyRateLimitStrategy(daily_limit=1000)
        limiter = RateLimiter(daily_strategy)
        key = limiter.get_key('test-service', 'test-api-key')
        assert key == 'remaining-daily-limit-test-service-test-api-key'
