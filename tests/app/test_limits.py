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
    NoOpRateLimiter,
    NoOpRateLimitStrategy,
    RateLimitConfig,
    RateLimiter,
    ServiceRateLimiter,
    WindowedRateLimitStrategy,
    WindowType,
    _get_strategy_class,
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

    @patch('app.limits.RATE_LIMIT_STRATEGY', 'WindowedRateLimitStrategy')
    def test_build_key_format(self) -> None:
        """Test that the service rate limiter generates the correct Redis key format."""
        limiter = ServiceRateLimiter()
        key = limiter.get_key('service-id', 'api-key-id')
        assert key == 'rate-limit-service-id-api-key-id'

    @patch('app.limits.RATE_LIMIT_STRATEGY', 'WindowedRateLimitStrategy')
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

    @patch('app.limits.RATE_LIMIT_STRATEGY', 'WindowedRateLimitStrategy')
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
        'error_type',
        [
            NonRetryableError('non-retryable failure'),
            RetryableError('temporary failure'),
        ],
    )
    @patch('app.limits.RATE_LIMIT_STRATEGY', 'WindowedRateLimitStrategy')
    async def test_error_handling_fail_open(
        self,
        mock_context: Tuple[str, str],
        make_request_with_redis: Callable[[Mock], StarletteRequest],
        error_type: Exception,
    ) -> None:
        """Should allow requests when consume token throws errors (fail-open behavior)."""
        service_id, api_key_id = mock_context
        limiter = ServiceRateLimiter()

        redis_mock = Mock(spec=RedisClientManager)
        redis_mock.consume_rate_limit_token = AsyncMock(side_effect=error_type)

        request = make_request_with_redis(redis_mock)

        await limiter(request)

        redis_mock.consume_rate_limit_token.assert_awaited_once_with(
            f'rate-limit-{service_id}-{api_key_id}',
            limiter.limit,
            limiter.window,
        )


class TestDailyRateLimiter:
    """Test the daily rate limiter factory function."""

    @patch('app.limits.RATE_LIMIT_STRATEGY', 'WindowedRateLimitStrategy')
    def test_build_daily_key_format(self) -> None:
        """Test that the daily rate limiter generates the correct Redis key format."""
        limiter = DailyRateLimiter()
        key = limiter.get_key('service-id', 'api-key-id')
        assert key == 'remaining-daily-limit-service-id-api-key-id'

    @patch('app.limits.RATE_LIMIT_STRATEGY', 'WindowedRateLimitStrategy')
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

    @patch('app.limits.RATE_LIMIT_STRATEGY', 'WindowedRateLimitStrategy')
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
        ('env_value', 'expected_limit'),
        [
            ('500', 500),
            (None, 1000),  # default value
        ],
    )
    @patch('app.limits.RATE_LIMIT_STRATEGY', 'WindowedRateLimitStrategy')
    def test_limit_initialization(self, env_value: str | None, expected_limit: int) -> None:
        """Test that daily limit is properly initialized from environment variable or default."""
        with patch('app.limits.os.getenv') as mock_getenv:
            # Configure side_effect for both calls to os.getenv
            if env_value is None:
                mock_getenv.side_effect = [1000, 'not set']  # Use default, then logging
            else:
                mock_getenv.side_effect = [env_value, env_value]  # Use provided value

            limiter = DailyRateLimiter()
            assert limiter.limit == expected_limit


class TestRateLimiter:
    """Test the RateLimiter class with different strategies."""

    @pytest.mark.parametrize(
        ('window_type', 'window_duration', 'expected_window'),
        [
            (WindowType.FIXED, 60, 60),
            (WindowType.DAILY, None, None),
        ],
    )
    def test_window_property(
        self, window_type: WindowType, window_duration: int | None, expected_window: int | None
    ) -> None:
        """Test that window property returns the correct value for different strategies."""
        config = RateLimitConfig(limit=10, window_type=window_type, window_duration=window_duration)
        strategy = WindowedRateLimitStrategy(config)
        limiter = RateLimiter(strategy)
        assert limiter.window == expected_window

    def test_get_key_delegates_to_strategy(self) -> None:
        """Test that get_key delegates to the underlying strategy and verifies key patterns."""
        # Test with service strategy (fixed window)
        service_config = RateLimitConfig(limit=5, window_type=WindowType.FIXED, window_duration=30)
        service_strategy = WindowedRateLimitStrategy(service_config)
        limiter = RateLimiter(service_strategy)
        key = limiter.get_key('test-service', 'test-api-key')
        assert key == 'rate-limit-test-service-test-api-key'

        # Test with daily strategy
        daily_config = RateLimitConfig(limit=1000, window_type=WindowType.DAILY)
        daily_strategy = WindowedRateLimitStrategy(daily_config)
        limiter = RateLimiter(daily_strategy)
        key = limiter.get_key('test-service', 'test-api-key')
        assert key == 'remaining-daily-limit-test-service-test-api-key'


class TestWindowedRateLimitStrategy:
    """Test the WindowedRateLimitStrategy class directly."""

    def test_fixed_window_validation(self) -> None:
        """Test that FIXED window type validation works correctly."""
        # Should work with window_duration provided
        config = RateLimitConfig(limit=10, window_type=WindowType.FIXED, window_duration=60)
        strategy = WindowedRateLimitStrategy(config)
        assert strategy.limit == 10
        assert strategy.window_duration == 60

        # Should raise ValueError when window_duration is None for FIXED type
        with pytest.raises(ValueError, match='window_duration is required for FIXED window type'):
            RateLimitConfig(limit=10, window_type=WindowType.FIXED, window_duration=None)

        # Test validation in WindowedRateLimitStrategy.__init__
        config = RateLimitConfig(limit=10, window_type=WindowType.DAILY)
        config.window_type = WindowType.FIXED
        config.window_duration = None

        with pytest.raises(ValueError, match='window_duration is required for FIXED window type'):
            WindowedRateLimitStrategy(config)

    def test_daily_expiry_calculation(self) -> None:
        """Test that daily expiry correctly calculates seconds until midnight UTC."""
        import datetime
        from unittest.mock import patch

        config = RateLimitConfig(limit=1000, window_type=WindowType.DAILY)
        strategy = WindowedRateLimitStrategy(config)

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

    @pytest.mark.parametrize(
        ('window_type', 'expected_message'),
        [
            (WindowType.FIXED, RESPONSE_429),
            (WindowType.DAILY, 'Daily rate limit exceeded'),
        ],
    )
    def test_get_error_message(self, window_type: WindowType, expected_message: str) -> None:
        """Test error messages for different window types."""
        if window_type == WindowType.FIXED:
            config = RateLimitConfig(limit=5, window_type=window_type, window_duration=30)
        else:
            config = RateLimitConfig(limit=1000, window_type=window_type)

        strategy = WindowedRateLimitStrategy(config)
        assert strategy.get_error_message() == expected_message

    async def test_is_allowed_delegates_to_redis(self) -> None:
        """Test that is_allowed properly delegates to Redis client."""
        config = RateLimitConfig(limit=5, window_type=WindowType.FIXED, window_duration=30)
        strategy = WindowedRateLimitStrategy(config)

        redis_mock = Mock(spec=RedisClientManager)
        redis_mock.consume_rate_limit_token = AsyncMock(return_value=True)

        result = await strategy.is_allowed(redis_mock, 'test-service', 'test-api-key')

        assert result is True
        redis_mock.consume_rate_limit_token.assert_awaited_once_with('rate-limit-test-service-test-api-key', 5, 30)

    def test_unsupported_window_type_error(self) -> None:
        """Test that unsupported window types raise ValueError."""
        config = RateLimitConfig(limit=100, window_type=WindowType.DAILY)
        strategy = WindowedRateLimitStrategy(config)

        # Temporarily change the window type to simulate an unsupported type
        strategy.window_type = 'unsupported'  # type: ignore[assignment]

        # Should raise ValueError for unsupported window type
        with pytest.raises(ValueError, match='Unsupported window type: unsupported'):
            strategy._calculate_window_expiry()


class TestRateLimiterBehavior:
    """Test RateLimiter behavior with different failure modes."""

    async def test_fail_closed_behavior(self) -> None:
        """Test that RateLimiter can be configured to fail closed (block requests on Redis errors)."""
        config = RateLimitConfig(limit=5, window_type=WindowType.FIXED, window_duration=30)
        strategy = WindowedRateLimitStrategy(config)
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
        config = RateLimitConfig(limit=5, window_type=WindowType.FIXED, window_duration=30)
        strategy = WindowedRateLimitStrategy(config)
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


class TestDynamicStrategyLoading:
    """Test the dynamic strategy loading functionality."""

    @pytest.mark.parametrize(
        ('strategy_name', 'expected_class'),
        [
            ('WindowedRateLimitStrategy', WindowedRateLimitStrategy),
            ('NoOpRateLimitStrategy', NoOpRateLimitStrategy),
        ],
    )
    def test_get_strategy_class_valid_strategies(self, strategy_name: str, expected_class: type) -> None:
        """Test that _get_strategy_class returns correct strategy classes for valid names."""
        strategy_class = _get_strategy_class(strategy_name)
        assert strategy_class == expected_class

    @pytest.mark.parametrize(
        ('invalid_name', 'expected_error_pattern'),
        [
            ('InvalidStrategy', 'Unknown rate limiting strategy: InvalidStrategy'),
            ('WindowType', 'WindowType is not a valid RateLimitStrategy'),
            ('dict', 'Unknown rate limiting strategy: dict'),
        ],
    )
    def test_get_strategy_class_invalid_names_raise_errors(
        self, invalid_name: str, expected_error_pattern: str
    ) -> None:
        """Test that _get_strategy_class raises ValueError for invalid strategy names."""
        with pytest.raises(ValueError, match=expected_error_pattern):
            _get_strategy_class(invalid_name)

    @pytest.mark.parametrize(
        ('factory_function', 'strategy_name', 'expected_class', 'expected_window_type'),
        [
            (ServiceRateLimiter, 'WindowedRateLimitStrategy', WindowedRateLimitStrategy, WindowType.FIXED),
            (ServiceRateLimiter, 'NoOpRateLimitStrategy', NoOpRateLimitStrategy, None),
            (DailyRateLimiter, 'WindowedRateLimitStrategy', WindowedRateLimitStrategy, WindowType.DAILY),
            (DailyRateLimiter, 'NoOpRateLimitStrategy', NoOpRateLimitStrategy, None),
        ],
    )
    def test_rate_limiter_strategy_selection(
        self,
        factory_function: Callable[[], RateLimiter],
        strategy_name: str,
        expected_class: type,
        expected_window_type: WindowType | None,
    ) -> None:
        """Test rate limiter factories create correct strategy based on configuration."""
        with patch('app.limits.RATE_LIMIT_STRATEGY', strategy_name):
            limiter = factory_function()
            assert isinstance(limiter.strategy, expected_class)

            if expected_window_type is not None and isinstance(limiter.strategy, WindowedRateLimitStrategy):
                assert limiter.strategy.window_type == expected_window_type

    @pytest.mark.parametrize(
        ('factory_function', 'strategy_name'),
        [
            (ServiceRateLimiter, 'InvalidStrategy'),
            (DailyRateLimiter, 'InvalidStrategy'),
        ],
    )
    def test_factory_functions_fallback_to_noop_on_invalid_strategy(
        self, factory_function: Callable[[], RateLimiter], strategy_name: str
    ) -> None:
        """Test that factory functions fall back to NoOp strategy for invalid strategy names."""
        with patch('app.limits.RATE_LIMIT_STRATEGY', strategy_name):
            with patch('app.limits.logger') as mock_logger:
                limiter = factory_function()
                assert isinstance(limiter.strategy, NoOpRateLimitStrategy)
                mock_logger.error.assert_called_once()
                error_message = str(mock_logger.error.call_args)
                assert 'Failed to load' in error_message
                assert strategy_name in error_message

    @patch.dict('os.environ', {'RATE_LIMIT_STRATEGY': 'NoOpRateLimitStrategy'})
    def test_environment_variable_integration(self) -> None:
        """Test that environment variable controls strategy selection."""
        # Need to reload the module to pick up the new environment variable
        import importlib

        import app.limits

        importlib.reload(app.limits)

        limiter = app.limits.ServiceRateLimiter()
        assert isinstance(limiter.strategy, app.limits.NoOpRateLimitStrategy)

    @pytest.mark.parametrize(
        ('factory_function', 'expected_class_name', 'env_vars'),
        [
            (ServiceRateLimiter, 'WindowedRateLimitStrategy', {'RATE_LIMIT_STRATEGY': 'WindowedRateLimitStrategy'}),
            (DailyRateLimiter, 'WindowedRateLimitStrategy', {'DAILY_RATE_LIMIT': '500'}),
        ],
    )
    def test_limiter_environment_variable_usage(
        self,
        factory_function: Callable[[], RateLimiter],
        expected_class_name: str,
        env_vars: dict[str, str],
    ) -> None:
        """Test that rate limiters use environment variables for configuration."""
        with patch('app.limits.RATE_LIMIT_STRATEGY', 'WindowedRateLimitStrategy'):
            with patch.dict('os.environ', env_vars, clear=False):
                limiter = factory_function()
                assert limiter.strategy.__class__.__name__ == expected_class_name


class TestNoOpRateLimitStrategy:
    """Test the NoOpRateLimitStrategy class."""

    def test_noop_strategy_behavior(self) -> None:
        """Test NoOpRateLimitStrategy key generation and error message."""
        config = RateLimitConfig(limit=0)
        strategy = NoOpRateLimitStrategy(config)

        # Test key generation
        key = strategy.get_key('test-service', 'test-api-key')
        assert key == 'noop-test-service-test-api-key'

        # Test error message
        assert strategy.get_error_message() == 'Rate limit exceeded'


class TestNoOpRateLimiter:
    """Test the NoOpRateLimiter class."""

    def test_noop_rate_limiter_factory(self) -> None:
        """Test NoOpRateLimiter factory function."""
        limiter = NoOpRateLimiter()
        assert type(limiter.strategy).__name__ == 'NoOpRateLimitStrategy'
        assert limiter.fail_open is True
        assert limiter.strategy.limit == 0
