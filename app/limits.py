"""Rate limiting dependency."""

import datetime
import os
from abc import ABC, abstractmethod
from enum import Enum
from typing import Type

from fastapi import HTTPException, Request, status
from loguru import logger
from starlette_context import context

from app.clients.redis_client import RedisClientManager
from app.constants import RESPONSE_429
from app.exceptions import NonRetryableError, RetryableError

RATE_LIMIT = int(os.getenv('RATE_LIMIT', 5))
OBSERVATION_PERIOD = int(os.getenv('OBSERVATION_PERIOD', 30))
DAILY_RATE_LIMIT = int(os.getenv('DAILY_RATE_LIMIT', 1000))

# Environment variable to control which rate limiting strategy to use
# Options: 'WindowedRateLimitStrategy' (default), 'NoOpRateLimitStrategy'
RATE_LIMIT_STRATEGY = os.getenv('RATE_LIMIT_STRATEGY', 'WindowedRateLimitStrategy')


class WindowType(Enum):
    """Enumeration of supported window types for rate limiting."""

    FIXED = 'fixed'  # Fixed duration windows (e.g., 30s, 5m, 1h)
    DAILY = 'daily'  # Calendar day windows (reset at midnight UTC)


class RateLimitStrategy(ABC):
    """Abstract base class for rate limiting strategies."""

    def __init__(self) -> None:
        """Initialize the strategy."""
        self.limit: int
        self.window: int | None = None

    @abstractmethod
    async def is_allowed(self, redis: RedisClientManager, service_id: str, api_key_id: str) -> bool:
        """Check if the request is allowed under this rate limiting strategy.

        Args:
            redis: The Redis client manager
            service_id: The service identifier
            api_key_id: The API key identifier

        Returns:
            True if the request is allowed, False if rate limited
        """
        ...  # pragma: no cover

    @abstractmethod
    def get_key(self, service_id: str, api_key_id: str) -> str:
        """Get the Redis key for this rate limiting strategy.

        Args:
            service_id: The service identifier
            api_key_id: The API key identifier

        Returns:
            The Redis key for tracking this rate limit
        """
        ...  # pragma: no cover

    @abstractmethod
    def get_error_message(self) -> str:
        """Get the error message when rate limit is exceeded.

        Returns:
            The error message to return to the client
        """
        ...  # pragma: no cover


class NoOpRateLimitStrategy(RateLimitStrategy):
    """A no-op rate limiting strategy that always allows requests.

    Used in environments where Redis is not available or rate limiting is disabled.
    """

    def __init__(self, limit: int = 0) -> None:
        """Initialize the no-op strategy.

        Args:
            limit: The rate limit (for compatibility, but not enforced)
        """
        super().__init__()
        self.limit = limit

    async def is_allowed(self, redis: RedisClientManager, service_id: str, api_key_id: str) -> bool:
        """Always allow requests in no-op mode.

        Args:
            redis: The Redis client manager (unused)
            service_id: The service identifier (unused)
            api_key_id: The API key identifier (unused)

        Returns:
            Always True (no rate limiting enforced)
        """
        return True

    def get_key(self, service_id: str, api_key_id: str) -> str:
        """Return a dummy key for compatibility.

        Args:
            service_id: The service identifier
            api_key_id: The API key identifier

        Returns:
            A dummy key string
        """
        return f'noop-{service_id}-{api_key_id}'

    def get_error_message(self) -> str:
        """Return a generic error message (should not be used in no-op mode).

        Returns:
            A generic error message
        """
        return 'Rate limit exceeded'


class WindowedRateLimitStrategy(RateLimitStrategy):
    """Unified strategy for windowed rate limiting with flexible window types."""

    def __init__(self, limit: int, window_type: WindowType, window_duration: int | None = None) -> None:
        """Initialize with limit and window configuration.

        Args:
            limit: The rate limit (number of requests)
            window_type: The type of window (FIXED, DAILY)
            window_duration: Duration in seconds for FIXED windows (ignored for DAILY windows)

        Raises:
            ValueError: If window_duration is None for FIXED window type
        """
        super().__init__()
        self.limit = limit
        self.window_type = window_type
        self.window_duration = window_duration

        if window_type == WindowType.FIXED and window_duration is None:
            raise ValueError('window_duration is required for FIXED window type')

        # Set the window attribute for backwards compatibility
        self.window = window_duration if window_type == WindowType.FIXED else None

    def get_key(self, service_id: str, api_key_id: str) -> str:
        """Construct the Redis key for tracking request count.

        Args:
            service_id: The service identifier
            api_key_id: The API key identifier

        Returns:
            The Redis key for tracking request count
        """
        if self.window_type == WindowType.DAILY:
            return f'remaining-daily-limit-{service_id}-{api_key_id}'
        else:
            # For FIXED and other window types, use the original format
            return f'rate-limit-{service_id}-{api_key_id}'

    def _calculate_window_expiry(self) -> int:
        """Calculate the expiry time for the current window.

        Returns:
            The expiry time in seconds for the window

        Raises:
            ValueError: If an unsupported window type is used
        """
        if self.window_type == WindowType.FIXED:
            # For FIXED windows, we know window_duration is not None due to validation in __init__
            assert self.window_duration is not None, 'window_duration should not be None for FIXED window type'
            return self.window_duration
        elif self.window_type == WindowType.DAILY:
            return self._calculate_daily_expiry()
        else:
            raise ValueError(f'Unsupported window type: {self.window_type}')

    def _calculate_daily_expiry(self) -> int:
        """Calculate expiry for daily windows (reset at midnight UTC).

        Returns:
            Seconds until midnight UTC
        """
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        next_reset = (now_utc + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        return int((next_reset - now_utc).total_seconds())

    async def is_allowed(self, redis: RedisClientManager, service_id: str, api_key_id: str) -> bool:
        """Check if request is allowed under windowed rate limits.

        Args:
            redis: The Redis client manager
            service_id: The service identifier
            api_key_id: The API key identifier

        Returns:
            True if the request is allowed, False if rate limited
        """
        key = self.get_key(service_id, api_key_id)
        window_expiry = self._calculate_window_expiry()
        return await redis.consume_rate_limit_token(key, self.limit, window_expiry)

    def get_error_message(self) -> str:
        """Get error message for rate limit exceeded.

        Returns:
            The error message for rate limits
        """
        if self.window_type == WindowType.DAILY:
            return 'Daily rate limit exceeded'
        else:
            return RESPONSE_429


class RateLimiter:
    """FastAPI dependency that enforces rate limiting using configurable strategies.

    Uses a strategy pattern to support different types of rate limiting (service-level, daily, etc.).
    Rate limiting is skipped if required request state values are missing.
    By default, if Redis is unavailable, requests are allowed through (fail-open behavior).
    This can be configured to block requests instead (fail-closed behavior).
    """

    def __init__(self, strategy: RateLimitStrategy, fail_open: bool = True) -> None:
        """Initialize with a rate limiting strategy.

        Args:
            strategy: The rate limiting strategy to use
            fail_open: Whether to allow requests when Redis fails. True = allow requests
                (fail-open), False = block requests with 429 error (fail-closed)
        """
        self.strategy = strategy
        self.fail_open = fail_open

    @property
    def limit(self) -> int:
        """Get the rate limit from the strategy."""
        return self.strategy.limit

    @property
    def window(self) -> int | None:
        """Get the window from the strategy (for service rate limiting)."""
        return getattr(self.strategy, 'window', None)

    async def __call__(self, request: Request) -> None:
        """Enforce rate limiting based on the configured strategy.

        Args:
            request: The FastAPI request object containing Redis client and context

        Raises:
            HTTPException: Raised with status code 429 if the rate limit is exceeded
        """
        redis: RedisClientManager = request.app.enp_state.redis_client_manager

        request_id = str(context['request_id'])
        service_id = str(context['service_id'])
        api_key_id = str(context['api_key_id'])

        try:
            allowed = await self.strategy.is_allowed(redis, service_id, api_key_id)
        except (NonRetryableError, RetryableError):
            self._log_error(request_id, service_id, api_key_id)
            allowed = self.fail_open

        if not allowed:
            self._log_rate_limited(request_id, service_id, api_key_id)
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=self.strategy.get_error_message())

    def get_key(self, service_id: str, api_key_id: str) -> str:
        """Get the Redis key for this rate limiter's strategy.

        Args:
            service_id: The service identifier
            api_key_id: The API key identifier

        Returns:
            The Redis key for tracking this rate limit
        """
        return self.strategy.get_key(service_id, api_key_id)

    def _log_error(self, request_id: str, service_id: str, api_key_id: str) -> None:
        """Log rate limiting errors."""
        logger.error(
            'Rate limiting failed for request_id: {}, service_id: {}, api_key_id: {}, allowing request by default',
            request_id,
            service_id,
            api_key_id,
        )

    def _log_rate_limited(self, request_id: str, service_id: str, api_key_id: str) -> None:
        """Log when requests are rate limited."""
        logger.debug(
            'Request rate limited for request_id: {}, service_id: {}, api_key_id: {}',
            request_id,
            service_id,
            api_key_id,
        )


def _get_strategy_class(strategy_name: str) -> Type[RateLimitStrategy]:
    """Dynamically load a rate limiting strategy class by name.

    Args:
        strategy_name: The name of the strategy class to load

    Returns:
        The strategy class

    Raises:
        ValueError: If the strategy name is not found or not a valid RateLimitStrategy
    """
    # Only allow strategy classes from this module for security
    current_module = globals()

    if strategy_name not in current_module:
        raise ValueError(f'Unknown rate limiting strategy: {strategy_name}')

    strategy_class = current_module[strategy_name]

    # Ensure it's a subclass of RateLimitStrategy
    if not (isinstance(strategy_class, type) and issubclass(strategy_class, RateLimitStrategy)):
        raise ValueError(f'{strategy_name} is not a valid RateLimitStrategy')

    return strategy_class


# Factory functions for common rate limiter configurations
def ServiceRateLimiter() -> RateLimiter:
    """Create a service-level rate limiter using environment variables.

    Uses RATE_LIMIT (default: 5) requests per OBSERVATION_PERIOD (default: 30) seconds.
    Configured with fail-open behavior (allows requests when Redis is unavailable).
    Strategy is determined by RATE_LIMIT_STRATEGY environment variable.

    Returns:
        RateLimiter configured based on RATE_LIMIT_STRATEGY environment variable
    """
    try:
        strategy_class = _get_strategy_class(RATE_LIMIT_STRATEGY)

        strategy: RateLimitStrategy
        if strategy_class == NoOpRateLimitStrategy:
            logger.info(f'Service rate limiting disabled (strategy: {RATE_LIMIT_STRATEGY})')
            strategy = NoOpRateLimitStrategy(RATE_LIMIT)
        elif strategy_class == WindowedRateLimitStrategy:
            logger.debug(f'Service rate limiting enabled (strategy: {RATE_LIMIT_STRATEGY})')
            strategy = WindowedRateLimitStrategy(RATE_LIMIT, WindowType.FIXED, OBSERVATION_PERIOD)
        else:
            # Fallback for any future strategy types
            logger.warning(f'Unknown strategy {RATE_LIMIT_STRATEGY}, falling back to NoOp')
            strategy = NoOpRateLimitStrategy(RATE_LIMIT)

        return RateLimiter(strategy, fail_open=True)

    except ValueError as e:
        logger.error(f'Failed to load rate limiting strategy {RATE_LIMIT_STRATEGY}: {e}. Falling back to NoOp.')
        strategy = NoOpRateLimitStrategy(RATE_LIMIT)
        return RateLimiter(strategy, fail_open=True)


def DailyRateLimiter() -> RateLimiter:
    """Create a daily rate limiter using environment variables.

    Uses DAILY_RATE_LIMIT (default: 1000) requests per day, resetting at midnight UTC.
    Configured with fail-open behavior (allows requests when Redis is unavailable).
    Strategy is determined by RATE_LIMIT_STRATEGY environment variable.

    Returns:
        RateLimiter configured based on RATE_LIMIT_STRATEGY environment variable
    """
    daily_limit = int(os.getenv('DAILY_RATE_LIMIT', 1000))

    try:
        strategy_class = _get_strategy_class(RATE_LIMIT_STRATEGY)

        strategy: RateLimitStrategy
        if strategy_class == NoOpRateLimitStrategy:
            logger.info(
                f'Daily rate limiting disabled (strategy: {RATE_LIMIT_STRATEGY}, would have been {daily_limit} requests/day)'
            )
            strategy = NoOpRateLimitStrategy(daily_limit)
        elif strategy_class == WindowedRateLimitStrategy:
            logger.debug(
                f'DailyRateLimiter created with limit: {daily_limit} (strategy: {RATE_LIMIT_STRATEGY}, from env: {os.getenv("DAILY_RATE_LIMIT", "not set")})'
            )
            strategy = WindowedRateLimitStrategy(daily_limit, WindowType.DAILY)
        else:
            # Fallback for any future strategy types
            logger.warning(f'Unknown strategy {RATE_LIMIT_STRATEGY}, falling back to NoOp')
            strategy = NoOpRateLimitStrategy(daily_limit)

        return RateLimiter(strategy, fail_open=True)

    except ValueError as e:
        logger.error(f'Failed to load daily rate limiting strategy {RATE_LIMIT_STRATEGY}: {e}. Falling back to NoOp.')
        strategy = NoOpRateLimitStrategy(daily_limit)
        return RateLimiter(strategy, fail_open=True)


def NoOpRateLimiter() -> RateLimiter:
    """Create a no-op rate limiter (always allows requests).

    Used in environments where Redis is not available or rate limiting is disabled.

    Returns:
        RateLimiter configured with a no-op strategy
    """
    strategy = NoOpRateLimitStrategy()
    return RateLimiter(strategy, fail_open=True)
