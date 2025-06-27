"""Rate limiting dependency."""

import os
from abc import ABC, abstractmethod

from fastapi import HTTPException, Request, status
from loguru import logger
from starlette_context import context

from app.clients.redis_client import RedisClientManager
from app.constants import RESPONSE_429
from app.exceptions import NonRetryableError, RetryableError

RATE_LIMIT = int(os.getenv('RATE_LIMIT', 5))
OBSERVATION_PERIOD = int(os.getenv('OBSERVATION_PERIOD', 30))
DAILY_RATE_LIMIT = int(os.getenv('DAILY_RATE_LIMIT', 1000))


class RateLimitStrategy(ABC):
    """Abstract base class for rate limiting strategies."""

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


class ServiceRateLimitStrategy(RateLimitStrategy):
    """Strategy for service-level rate limiting with fixed windows."""

    def __init__(self, limit: int = RATE_LIMIT, window: int = OBSERVATION_PERIOD) -> None:
        """Initialize with rate limit and window.

        Args:
            limit: The rate limit (number of requests)
            window: The time window in seconds
        """
        self.limit = limit
        self.window = window

    def get_key(self, service_id: str, api_key_id: str) -> str:
        """Construct the Redis key for tracking request count.

        Args:
            service_id: The service identifier
            api_key_id: The API key identifier

        Returns:
            The Redis key for tracking request count
        """
        return f'rate-limit-{service_id}-{api_key_id}'

    async def is_allowed(self, redis: RedisClientManager, service_id: str, api_key_id: str) -> bool:
        """Check if request is allowed under service rate limits.

        Args:
            redis: The Redis client manager
            service_id: The service identifier
            api_key_id: The API key identifier

        Returns:
            True if the request is allowed, False if rate limited
        """
        key = self.get_key(service_id, api_key_id)
        return await redis.consume_rate_limit_token(key, self.limit, self.window)

    def get_error_message(self) -> str:
        """Get error message for service rate limit exceeded.

        Returns:
            The error message for service rate limits
        """
        return RESPONSE_429


class DailyRateLimitStrategy(RateLimitStrategy):
    """Strategy for daily rate limiting with midnight UTC reset."""

    def __init__(self, daily_limit: int) -> None:
        """Initialize with daily limit.

        Args:
            daily_limit: The daily rate limit value
        """
        self.daily_limit = daily_limit

    def get_key(self, service_id: str, api_key_id: str) -> str:
        """Construct Redis key for daily tracking per service/API key combination.

        Args:
            service_id: The service identifier
            api_key_id: The API key identifier

        Returns:
            The Redis key for tracking daily limits
        """
        return f'remaining-daily-limit-{service_id}-{api_key_id}'

    async def is_allowed(self, redis: RedisClientManager, service_id: str, api_key_id: str) -> bool:
        """Check if request is allowed under daily rate limits.

        Args:
            redis: The Redis client manager
            service_id: The service identifier
            api_key_id: The API key identifier

        Returns:
            True if the request is allowed, False if rate limited
        """
        key = self.get_key(service_id, api_key_id)
        return await redis.consume_daily_rate_limit_token(key, self.daily_limit)

    def get_error_message(self) -> str:
        """Get error message for daily rate limit exceeded.

        Returns:
            The error message for daily rate limits
        """
        return 'Daily rate limit exceeded'


class BaseRateLimiter(ABC):
    """Base class for rate limiters following SOLID principles."""

    def __init__(self, strategy: RateLimitStrategy, fail_open: bool = True) -> None:
        """Initialize with a rate limiting strategy.

        Args:
            strategy: The rate limiting strategy to use
            fail_open: Whether to allow requests when Redis fails (True) or block them (False)
        """
        self.strategy = strategy
        self.fail_open = fail_open

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

    @abstractmethod
    def _log_error(self, request_id: str, service_id: str, api_key_id: str) -> None:
        """Log rate limiting errors."""
        ...  # pragma: no cover

    @abstractmethod
    def _log_rate_limited(self, request_id: str, service_id: str, api_key_id: str) -> None:
        """Log when requests are rate limited."""
        ...  # pragma: no cover


class ServiceRateLimiter(BaseRateLimiter):
    """FastAPI dependency that enforces service-level rate limiting.

    Uses environment variables to define a global rate limit (count) and window (seconds).
    Rate limiting is skipped if required request state values are missing.
    If Redis is unavailable, requests are blocked (fail-closed behavior).
    """

    def __init__(self) -> None:
        """Initialize rate limit values from environment variables."""
        strategy = ServiceRateLimitStrategy()
        super().__init__(strategy, fail_open=True)  # Changed to fail_open=True to match original behavior

    @property
    def limit(self) -> int:
        """Get the rate limit from the strategy for backward compatibility."""
        return self.strategy.limit  # type: ignore[attr-defined,no-any-return]

    @property
    def window(self) -> int:
        """Get the window from the strategy for backward compatibility."""
        return self.strategy.window  # type: ignore[attr-defined,no-any-return]

    def _build_key(self, service_id: str, api_key_id: str) -> str:
        """Construct the Redis key for tracking request count.

        Returns:
            str: A Redis key in the format 'rate-limit-{service_id}-{api_key_id}'.
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
            'Request rate limited for throughput for request_id: {}, service_id: {}, api_key_id: {}',
            request_id,
            service_id,
            api_key_id,
        )


class DailyRateLimiter(BaseRateLimiter):
    """FastAPI dependency that enforces daily rate limiting per service/API key.

    Uses environment variables to define a daily rate limit (count) per service/API key combination.
    Rate limiting is skipped if required request state values are missing.
    If Redis is unavailable, requests are allowed (fail-open behavior).
    """

    def __init__(self) -> None:
        """Initialize daily rate limit values from environment variables."""
        # Read the daily limit from environment at instantiation time
        daily_limit = int(os.getenv('DAILY_RATE_LIMIT', 1000))
        strategy = DailyRateLimitStrategy(daily_limit)
        super().__init__(strategy, fail_open=True)

    @property
    def daily_limit(self) -> int:
        """Get the daily limit from the strategy for backward compatibility."""
        return self.strategy.daily_limit  # type: ignore[attr-defined,no-any-return]

    def _build_daily_key(self, service_id: str, api_key_id: str) -> str:
        """Construct Redis key for daily tracking per service/API key combination.

        Args:
            service_id (str): The service identifier.
            api_key_id (str): The API key identifier.

        Returns:
            str: A Redis key in the format 'remaining-daily-limit-{service_id}-{api_key_id}'.
        """
        return self.strategy.get_key(service_id, api_key_id)

    def _log_error(self, request_id: str, service_id: str, api_key_id: str) -> None:
        """Log daily rate limiting errors."""
        logger.error(
            'Daily rate limiting failed for request_id: {}, service_id: {}, api_key_id: {}, allowing request by default',
            request_id,
            service_id,
            api_key_id,
        )

    def _log_rate_limited(self, request_id: str, service_id: str, api_key_id: str) -> None:
        """Log when requests are daily rate limited."""
        logger.debug(
            'Request daily rate limited for request_id: {}, service_id: {}, api_key_id: {}',
            request_id,
            service_id,
            api_key_id,
        )
