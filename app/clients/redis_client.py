"""Redis client manager that encapsulates Redis interactions and handles retryable/non-retryable errors."""

from typing import Awaitable, Callable, TypeVar

from loguru import logger
from redis.asyncio import ConnectionPool, Redis
from redis.exceptions import ConnectionError, RedisError, TimeoutError
from tenacity import retry, retry_if_exception_type, stop_after_attempt

from app.exceptions import NonRetryableError, RetryableError
from app.providers.utils import log_on_retry

_MAX_REDIS_RETRIES = 3  # Arbitrary

F = TypeVar('F', bound=Callable[..., Awaitable[bool]])


def redis_retry() -> Callable[[F], F]:
    """Return a retry decorator for Redis operations with typed support.

    This decorator wraps an asynchronous function and retries it if a `RetryableError` is raised.
    It uses the `tenacity` retry strategy, logging before each retry attempt and retrying up to
    `_MAX_REDIS_RETRIES` times before re-raising the exception.

    Type Hint:
        Returns a decorator that can be applied to any `async def` function that returns `bool`.

    Returns:
        Callable[[F], F]: A decorator that applies retry behavior to a coroutine function.
    """
    return retry(
        before_sleep=log_on_retry,
        reraise=True,
        retry=retry_if_exception_type(RetryableError),
        stop=stop_after_attempt(_MAX_REDIS_RETRIES),
    )


class RedisClientManager:
    """Manages a Redis connection pool and provides safe access to basic Redis commands.

    Encapsulates Redis operations and re-raises low-level exceptions as application-specific
    retryable or non-retryable errors to support fault-tolerant usage.
    """

    def __init__(self, redis_url: str) -> None:
        """Initialize the Redis client manager with a connection pool.

        Args:
            redis_url (str): The Redis connection URL.
        """
        self._pool = ConnectionPool.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=3,  # connection timeout in seconds, matching notification-api
            socket_timeout=3,  # command timeout in seconds, matching notification-api
        )
        self._client: Redis | None = None

    def get_client(self) -> Redis:
        """Lazily instantiate and return the Redis client.

        Returns:
            Redis: The Redis client instance.
        """
        if self._client is None:
            self._client = Redis(connection_pool=self._pool)
        return self._client

    @redis_retry()
    async def consume_rate_limit_token(self, key: str, limit: int, window: int) -> bool:
        """Attempt to consume a token for a fixed-window rate limiter.

        This method uses Redis to enforce rate limits by:
        - Setting the key to the specified limit with an expiry if it doesn't exist.
        - Checking the remaining token count.
        - Decrementing the token count if available.

        Args:
            key (str): The Redis key used to track the rate limit counter.
            limit (int): The maximum number of allowed actions per window.
            window (int): The duration of the rate limit window in seconds.

        Returns:
            bool: True if a token was successfully consumed (i.e., not rate limited),
                  False if the rate limit has been exceeded.

        Raises:
            RetryableError: If the Redis operation fails due to a transient issue (e.g., timeout or connection loss).
            NonRetryableError: If the Redis operation fails in a non-recoverable way.
        """
        is_allowed = False

        try:
            client = self.get_client()
            await client.set(name=key, value=limit, ex=window, nx=True)
            current = await client.get(key)

            if current and int(current) > 0:
                await client.decrby(name=key, amount=1)
                is_allowed = True

        except (ConnectionError, TimeoutError) as e:
            raise RetryableError('Redis rate limit operation failed (connection issue)') from e
        except RedisError as e:
            raise NonRetryableError('Redis rate limit operation failed') from e

        return is_allowed

    async def close(self) -> None:
        """Close the Redis client and connection pool gracefully.

        Logs and suppresses Redis shutdown errors to avoid breaking application shutdown.
        """
        try:
            if self._client:
                await self._client.close()
            await self._pool.disconnect()
        except RedisError:
            logger.exception('Redis shutdown failed')
