"""Rate limiting dependency."""

import os

from fastapi import HTTPException, Request, status
from loguru import logger
from starlette_context import context

from app.clients.redis_client import RedisClientManager
from app.constants import RESPONSE_429
from app.exceptions import NonRetryableError, RetryableError

RATE_LIMIT = int(os.getenv('RATE_LIMIT', 5))
OBSERVATION_PERIOD = int(os.getenv('OBSERVATION_PERIOD', 30))


class ServiceRateLimiter:
    """FastAPI dependency that enforces service-level rate limiting.

    Uses environment variables to define a global rate limit (count) and window (seconds).
    Rate limiting is skipped if required request state values are missing.
    If Redis is unavailable, requests are blocked (fail-closed behavior).
    """

    def __init__(self) -> None:
        """Initialize rate limit values from environment variables."""
        self.limit = RATE_LIMIT
        self.window = OBSERVATION_PERIOD

    def _build_key(self, service_id: str, api_key_id: str) -> str:
        """Construct the Redis key for tracking request count.

        Returns:
            str: A Redis key in the format 'rate-limit-{service_id}-{api_key_id}'.
        """
        return f'rate-limit-{service_id}-{api_key_id}'

    async def __call__(self, request: Request) -> None:
        """Enforce rate limiting based on service and API key identifiers in request state.

        Context values set upon successful service token authorization
        Defaulting to ALLOW for NonRetryableError and RetryableError to avoid limiting if redis fails

        Args:
            request (Request): The FastAPI request object. This must contain:
                - `app.enp_state.redis_client`: An instance of RedisClientManager.
                - Context values for 'service_id' and 'api_user' (e.g., via starlette_context),
                where 'api_user.id' is used as the API key identifier.

        Raises:
            HTTPException: Raised with status code 429 if the rate limit is exceeded
                        or if Redis errors occur (fail-closed behavior).
        """
        redis: RedisClientManager = request.app.enp_state.redis_client_manager

        request_id = str(context['request_id'])
        service_id = str(context['service_id'])
        api_key_id = str(context['api_key_id'])

        key = self._build_key(service_id, api_key_id)

        try:
            allowed = await redis.consume_rate_limit_token(key, self.limit, self.window)
        except (NonRetryableError, RetryableError):
            logger.error(
                'Rate limiting failed for request_id: {}, service_id: {}, api_key_id: {}, allowing request by default',
                request_id,
                service_id,
                api_key_id,
            )
            # default to allow, we don't want to limit is redis is having problems
            allowed = True

        if not allowed:
            logger.debug(
                'Request rate limited for throughput for request_id: {}, service_id: {}, api_key_id: {}',
                request_id,
                service_id,
                api_key_id,
            )
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=RESPONSE_429)
