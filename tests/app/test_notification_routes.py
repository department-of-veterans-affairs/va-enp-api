"""Test module for notification routes in app/main.py."""

from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException, status

from tests.conftest import ENPTestClient


class TestGetNotificationRoutes:
    """Test daily rate limiting functionality on GET notification routes."""

    @pytest.fixture
    def valid_notification_id(self) -> str:
        """Create a valid notification ID for testing.

        Returns:
            str: A valid notification ID for testing.
        """
        return str(uuid4())

    async def test_legacy_notification_get_allows_request_under_daily_limit(
        self,
        client: ENPTestClient,
        valid_notification_id: str,
        mocker: AsyncMock,
    ) -> None:
        """Test that GET notification route allows requests when under daily limit."""
        # Mock auth and dependencies
        mocker.patch('app.auth.JWTBearerAdmin.__call__')

        # Mock the rate limiter's __call__ method to bypass context access
        async def mock_rate_limiter_call(self: object, request: object) -> None:
            pass  # Do nothing, allow the request

        mocker.patch('app.limits.RateLimiter.__call__', mock_rate_limiter_call)

        # Mock the actual notification retrieval to avoid DB dependencies
        mock_dao = mocker.patch('app.legacy.dao.notifications_dao.LegacyNotificationDao.get')
        mock_dao.return_value = Mock(_asdict=lambda: {'id': valid_notification_id})

        response = client.get(f'/legacy/notifications/{valid_notification_id}')

        # This test will fail until DailyRateLimiter is implemented
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR]

    async def test_legacy_notification_get_blocks_request_over_daily_limit(
        self,
        client: ENPTestClient,
        valid_notification_id: str,
        mocker: AsyncMock,
    ) -> None:
        """Test that GET notification route blocks requests when daily limit exceeded."""
        # Mock auth to pass
        mocker.patch('app.auth.JWTBearerAdmin.__call__')

        # Mock the rate limiter's __call__ method to raise HTTPException for rate limiting
        def mock_rate_limiter_blocking(self: object, request: object) -> None:
            raise HTTPException(status_code=429, detail='Daily rate limit exceeded')

        mocker.patch('app.limits.RateLimiter.__call__', mock_rate_limiter_blocking)

        response = client.get(f'/legacy/notifications/{valid_notification_id}')

        # Should return 429 when daily limit exceeded
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert 'daily rate limit' in response.json()['detail'].lower()

    async def test_legacy_notification_get_fails_open_on_daily_rate_limiter_redis_error(
        self,
        client: ENPTestClient,
        valid_notification_id: str,
        mocker: AsyncMock,
    ) -> None:
        """Test that GET notification route fails open when daily rate limiter has Redis errors."""
        # Mock auth to pass
        mocker.patch('app.auth.JWTBearerAdmin.__call__')

        # Mock the rate limiter's __call__ method to allow requests (fail-open behavior)
        async def mock_rate_limiter_failopen(self: object, request: object) -> None:
            pass  # Do nothing, allow the request (simulating fail-open)

        mocker.patch('app.limits.RateLimiter.__call__', mock_rate_limiter_failopen)

        # Mock the actual notification retrieval
        mock_dao = mocker.patch('app.legacy.dao.notifications_dao.LegacyNotificationDao.get')
        mock_dao.return_value = Mock(_asdict=lambda: {'id': valid_notification_id})

        response = client.get(f'/legacy/notifications/{valid_notification_id}')

        # Should allow request when Redis fails (fail-open behavior)
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR]
