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
    RateLimiter,
    ServiceRateLimiter,
    WindowedRateLimitStrategy,
    WindowType,
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
    """Test the service rate limiter factory function."""

    def test_build_key_format(self) -> None:
        """Test that the service rate limiter generates the correct Redis key format."""
        limiter = ServiceRateLimiter()
        key = limiter.get_key('service-id', 'api-key-id')
        assert key == 'rate-limit-service-id-api-key-id'

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
    """Test the daily rate limiter factory function."""

    def test_build_daily_key_format(self) -> None:
        """Test that the daily rate limiter generates the correct Redis key format."""
        limiter = DailyRateLimiter()
        key = limiter.get_key('service-id', 'api-key-id')
        assert key == 'remaining-daily-limit-service-id-api-key-id'

    async def test_allows_request_under_daily_limit(
        self,
        mock_context: Tuple[str, str],
        make_request_with_redis: Callable[[Mock], StarletteRequest],
    ) -> None:
        """Should allow the request when consume daily token returns True (token was consumed)."""
        service_id, api_key_id = mock_context
        limiter = DailyRateLimiter()

        redis_mock = Mock(spec=RedisClientManager)
        redis_mock.consume_rate_limit_token = AsyncMock(return_value=True)

        request = make_request_with_redis(redis_mock)

        await limiter(request)

        # Should call consume_rate_limit_token with daily key and window expiry
        redis_mock.consume_rate_limit_token.assert_awaited_once()
        call_args = redis_mock.consume_rate_limit_token.call_args
        assert call_args[0][0] == f'remaining-daily-limit-{service_id}-{api_key_id}'  # key
        assert call_args[0][1] == limiter.limit  # limit
        assert isinstance(call_args[0][2], int)  # window_expiry (seconds until midnight)

    async def test_blocks_request_over_daily_limit(
        self,
        mock_context: Tuple[str, str],
        make_request_with_redis: Callable[[Mock], StarletteRequest],
    ) -> None:
        """Should raise 429 when consume daily token returns False (daily limit exceeded)."""
        limiter = DailyRateLimiter()

        redis_mock = Mock(spec=RedisClientManager)
        redis_mock.consume_rate_limit_token = AsyncMock(return_value=False)

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
        redis_mock.consume_rate_limit_token = AsyncMock(side_effect=raises)

        request = make_request_with_redis(redis_mock)

        # Should not raise an exception - fail open
        await limiter(request)

        # Should call consume_rate_limit_token with daily key and window expiry
        redis_mock.consume_rate_limit_token.assert_awaited_once()
        call_args = redis_mock.consume_rate_limit_token.call_args
        assert call_args[0][0] == f'remaining-daily-limit-{service_id}-{api_key_id}'  # key

    def test_limit_initialization_from_env(self) -> None:
        """Test that daily limit is properly initialized from environment variable."""
        with patch('app.limits.os.getenv') as mock_getenv:
            # Configure side_effect to return '500' for the first call, '500' for the second call (logging)
            mock_getenv.side_effect = ['500', '500']
            limiter = DailyRateLimiter()
            assert limiter.limit == 500
            # Verify os.getenv was called twice: once for the actual value, once for logging
            assert mock_getenv.call_count == 2
            mock_getenv.assert_any_call('DAILY_RATE_LIMIT', 1000)
            mock_getenv.assert_any_call('DAILY_RATE_LIMIT', 'not set')

    def test_limit_initialization_default(self) -> None:
        """Test that daily limit uses default value when environment variable is not set."""
        with patch('app.limits.os.getenv') as mock_getenv:
            # Configure side_effect to return the default value for the first call, 'not set' for the second
            mock_getenv.side_effect = [1000, 'not set']
            limiter = DailyRateLimiter()
            assert limiter.limit == 1000
            # Verify os.getenv was called twice: once for the actual value, once for logging
            assert mock_getenv.call_count == 2
            mock_getenv.assert_any_call('DAILY_RATE_LIMIT', 1000)
            mock_getenv.assert_any_call('DAILY_RATE_LIMIT', 'not set')


class TestRateLimiter:
    """Test the RateLimiter class with different strategies."""

    def test_window_property_with_service_strategy(self) -> None:
        """Test that window property returns the correct value for service strategy."""
        strategy = WindowedRateLimitStrategy(limit=10, window_type=WindowType.FIXED, window_duration=60)
        limiter = RateLimiter(strategy)
        assert limiter.window == 60

    def test_window_property_with_daily_strategy(self) -> None:
        """Test that window property returns None for daily strategy."""
        strategy = WindowedRateLimitStrategy(limit=1000, window_type=WindowType.DAILY)
        limiter = RateLimiter(strategy)
        assert limiter.window is None

    def test_get_key_delegates_to_strategy(self) -> None:
        """Test that get_key delegates to the underlying strategy."""
        # Test with service strategy
        service_strategy = WindowedRateLimitStrategy(limit=5, window_type=WindowType.FIXED, window_duration=30)
        limiter = RateLimiter(service_strategy)
        key = limiter.get_key('test-service', 'test-api-key')
        assert key == 'rate-limit-test-service-test-api-key'

        # Test with daily strategy
        daily_strategy = WindowedRateLimitStrategy(limit=1000, window_type=WindowType.DAILY)
        limiter = RateLimiter(daily_strategy)
        key = limiter.get_key('test-service', 'test-api-key')
        assert key == 'remaining-daily-limit-test-service-test-api-key'


class TestWindowedRateLimitStrategy:
    """Test the WindowedRateLimitStrategy class directly."""

    def test_fixed_window_requires_duration(self) -> None:
        """Test that FIXED window type requires window_duration parameter."""
        # Should work with window_duration provided
        strategy = WindowedRateLimitStrategy(limit=10, window_type=WindowType.FIXED, window_duration=60)
        assert strategy.limit == 10
        assert strategy.window_duration == 60

        # Should raise ValueError when window_duration is None for FIXED type
        with pytest.raises(ValueError, match='window_duration is required for FIXED window type'):
            WindowedRateLimitStrategy(limit=10, window_type=WindowType.FIXED, window_duration=None)

    def test_unsupported_window_type_error(self) -> None:
        """Test that unsupported window types raise ValueError."""
        # Create a strategy with a mock unsupported window type
        strategy = WindowedRateLimitStrategy(limit=100, window_type=WindowType.DAILY)

        # Temporarily change the window type to simulate an unsupported type
        strategy.window_type = 'unsupported'  # type: ignore[assignment]

        # Should raise ValueError for unsupported window type
        with pytest.raises(ValueError, match='Unsupported window type: unsupported'):
            strategy._calculate_window_expiry()

    def test_daily_expiry_calculation(self) -> None:
        """Test that daily expiry correctly calculates seconds until midnight UTC."""
        import datetime
        from unittest.mock import patch

        strategy = WindowedRateLimitStrategy(limit=1000, window_type=WindowType.DAILY)

        # Mock datetime.datetime.now to return a fixed time: 2023-06-27 14:30:00 UTC
        fixed_time = datetime.datetime(2023, 6, 27, 14, 30, 0, tzinfo=datetime.timezone.utc)

        with patch('app.limits.datetime.datetime') as mock_datetime:
            mock_datetime.now.return_value = fixed_time
            mock_datetime.timedelta = datetime.timedelta
            mock_datetime.timezone = datetime.timezone

            # Should calculate seconds until next midnight (2023-06-28 00:00:00)
            # From 14:30:00 to midnight = 9.5 hours = 34,200 seconds
            expiry = strategy._calculate_daily_expiry()
            assert isinstance(expiry, int)
            assert expiry == 34200  # 9.5 hours in seconds

    def test_get_error_message_fixed_window(self) -> None:
        """Test error message for fixed window rate limits."""
        strategy = WindowedRateLimitStrategy(limit=5, window_type=WindowType.FIXED, window_duration=30)
        assert strategy.get_error_message() == RESPONSE_429

    def test_get_error_message_daily_window(self) -> None:
        """Test error message for daily rate limits."""
        strategy = WindowedRateLimitStrategy(limit=1000, window_type=WindowType.DAILY)
        assert strategy.get_error_message() == 'Daily rate limit exceeded'

    def test_key_generation_patterns(self) -> None:
        """Test Redis key generation for different window types."""
        # Test fixed window key
        fixed_strategy = WindowedRateLimitStrategy(limit=5, window_type=WindowType.FIXED, window_duration=30)
        fixed_key = fixed_strategy.get_key('test-service', 'test-api-key')
        assert fixed_key == 'rate-limit-test-service-test-api-key'

        # Test daily window key
        daily_strategy = WindowedRateLimitStrategy(limit=1000, window_type=WindowType.DAILY)
        daily_key = daily_strategy.get_key('test-service', 'test-api-key')
        assert daily_key == 'remaining-daily-limit-test-service-test-api-key'

    async def test_is_allowed_delegates_to_redis(self) -> None:
        """Test that is_allowed properly delegates to Redis client."""
        strategy = WindowedRateLimitStrategy(limit=5, window_type=WindowType.FIXED, window_duration=30)

        redis_mock = Mock(spec=RedisClientManager)
        redis_mock.consume_rate_limit_token = AsyncMock(return_value=True)

        result = await strategy.is_allowed(redis_mock, 'test-service', 'test-api-key')

        assert result is True
        redis_mock.consume_rate_limit_token.assert_awaited_once_with('rate-limit-test-service-test-api-key', 5, 30)

    @pytest.mark.parametrize(
        ('window_type', 'expected_expiry_type'),
        [
            (WindowType.FIXED, int),
            (WindowType.DAILY, int),
        ],
    )
    def test_calculate_window_expiry_returns_int(self, window_type: WindowType, expected_expiry_type: type) -> None:
        """Test that window expiry calculation returns appropriate types."""
        if window_type == WindowType.FIXED:
            strategy = WindowedRateLimitStrategy(limit=10, window_type=window_type, window_duration=60)
        else:
            strategy = WindowedRateLimitStrategy(limit=1000, window_type=window_type)

        expiry = strategy._calculate_window_expiry()
        assert isinstance(expiry, expected_expiry_type)
        assert expiry > 0


class TestRateLimiterBehavior:
    """Test RateLimiter behavior with different failure modes."""

    async def test_fail_closed_behavior(self) -> None:
        """Test that RateLimiter can be configured to fail closed (block requests on Redis errors)."""
        strategy = WindowedRateLimitStrategy(limit=5, window_type=WindowType.FIXED, window_duration=30)
        limiter = RateLimiter(strategy, fail_open=False)

        redis_mock = Mock(spec=RedisClientManager)
        redis_mock.consume_rate_limit_token = AsyncMock(side_effect=RetryableError('Redis down'))

        request = StarletteRequest(
            scope={
                'type': 'http',
                'headers': Headers({}).raw,
                'app': Mock(enp_state=Mock(redis_client_manager=redis_mock)),
            }
        )

        with patch('app.limits.context', {'request_id': 'test', 'service_id': 'test', 'api_key_id': 'test'}):
            with pytest.raises(HTTPException) as exc_info:
                await limiter(request)

            assert exc_info.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    async def test_context_missing_values_handling(self) -> None:
        """Test behavior when required context values are missing."""
        strategy = WindowedRateLimitStrategy(limit=5, window_type=WindowType.FIXED, window_duration=30)
        limiter = RateLimiter(strategy)

        redis_mock = Mock(spec=RedisClientManager)
        request = StarletteRequest(
            scope={
                'type': 'http',
                'headers': Headers({}).raw,
                'app': Mock(enp_state=Mock(redis_client_manager=redis_mock)),
            }
        )

        # Test with missing context values
        with patch('app.limits.context', {}):
            with pytest.raises(KeyError):
                await limiter(request)

    def test_strategy_delegation(self) -> None:
        """Test that RateLimiter properly delegates to its strategy."""
        strategy = Mock()
        strategy.limit = 10
        strategy.window = 30
        strategy.get_key.return_value = 'test-key'

        limiter = RateLimiter(strategy)

        assert limiter.limit == 10
        assert limiter.window == 30
        assert limiter.get_key('service', 'api-key') == 'test-key'
        strategy.get_key.assert_called_once_with('service', 'api-key')
