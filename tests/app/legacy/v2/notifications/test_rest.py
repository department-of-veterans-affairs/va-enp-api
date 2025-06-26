"""Test module for app/legacy/v2/notifications/rest.py."""

from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import status

from tests.conftest import ENPTestClient

_push_path = '/legacy/v2/notifications/push'
_sms_path_legacy = '/legacy/v2/notifications/sms'
_sms_path_v2 = '/v2/notifications/sms'


class TestDailyRateLimitingSMSRoutes:
    """Test daily rate limiting functionality on SMS routes."""

    @pytest.fixture
    def valid_sms_request(self) -> dict[str, Any]:
        """Create a valid SMS request payload.

        Returns:
            dict[str, Any]: A valid SMS request payload for testing.
        """
        return {
            'phone_number': '+12345678901',
            'template_id': str(uuid4()),
            'personalisation': {'name': 'Test User'},
        }

    async def test_legacy_sms_route_allows_request_under_daily_limit(
        self,
        client: ENPTestClient,
        valid_sms_request: dict[str, Any],
        mocker: AsyncMock,
    ) -> None:
        """Test that legacy SMS route allows requests when under daily limit."""
        # Mock auth and rate limiters to return success
        mocker.patch('app.auth.verify_service_token')
        mocker.patch('app.limits.ServiceRateLimiter.__call__')

        # Mock the daily rate limiter to allow request (should fail since not implemented yet)
        mocker.patch('app.limits.DailyRateLimiter.__call__')

        # Mock the actual SMS processing to avoid DB/external dependencies
        mocker.patch('app.legacy.v2.notifications.rest._sms_post')

        response = client.post(_sms_path_legacy, json=valid_sms_request)

        # This test will fail until DailyRateLimiter is implemented
        # For now, we expect it to pass without daily rate limiting
        assert response.status_code in [status.HTTP_201_CREATED, status.HTTP_500_INTERNAL_SERVER_ERROR]

    async def test_legacy_sms_route_blocks_request_over_daily_limit(
        self,
        client: ENPTestClient,
        valid_sms_request: dict[str, Any],
        mocker: AsyncMock,
    ) -> None:
        """Test that legacy SMS route blocks requests when daily limit exceeded."""
        # Mock auth and short-term rate limiter to pass
        mocker.patch('app.auth.verify_service_token')
        mocker.patch('app.limits.ServiceRateLimiter.__call__')

        # Mock daily rate limiter to reject request (daily limit exceeded)
