"""Test module for notification routes in app/main.py."""

from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from fastapi import status

from tests.conftest import ENPTestClient


class TestGetNotificationRoutes:
    """Test GET notification routes functionality."""

    @pytest.fixture
    def valid_notification_id(self) -> str:
        """Create a valid notification ID for testing.

        Returns:
            str: A valid notification ID for testing.
        """
        return str(uuid4())

    async def test_legacy_notification_get_success(
        self,
        client: ENPTestClient,
        valid_notification_id: str,
        mocker: AsyncMock,
    ) -> None:
        """Test that GET notification route returns notification data successfully."""
        # Mock auth and dependencies
        mocker.patch('app.auth.JWTBearerAdmin.__call__')

        # Mock the actual notification retrieval to avoid DB dependencies
        mock_dao = mocker.patch('app.legacy.dao.notifications_dao.LegacyNotificationDao.get')
        mock_dao.return_value = Mock(_asdict=lambda: {'id': valid_notification_id})

        response = client.get(f'/legacy/notifications/{valid_notification_id}')

        # Should return 200 when the notification is found
        assert response.status_code == status.HTTP_200_OK
