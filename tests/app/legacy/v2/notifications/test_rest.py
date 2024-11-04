"""Test module for app/legacy/v2/notifications/rest.py."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.constants import MobileAppType
from app.legacy.v2.notifications.route_schema import (
    V2NotificationPushRequest,
    V2NotificationSingleRequest,
    V2NotificationSingleResponse,
)
from app.v3.notifications.rest import RESPONSE_400


def test_post(client: TestClient) -> None:
    """Test POST /v2/notifications/.

    Args:
        client(TestClient): FastAPI client fixture

    """
    srequest = V2NotificationSingleRequest(
        personalisation={'hello': 'world'},
        reference='test',
        template_id=uuid4(),
        to='vanotify@va.gov',
    )
    resp = client.post('v2/notifications', json=srequest.serialize())
    assert resp.status_code == status.HTTP_201_CREATED
    assert isinstance(V2NotificationSingleResponse.model_validate(resp.json()), V2NotificationSingleResponse)


def test_post_without_optional_fields(client: TestClient) -> None:
    """Test POST /v2/notifications/ without optional fields.

    Args:
        client(TestClient): FastAPI client fixture

    """
    request = V2NotificationSingleRequest(
        template_id=uuid4(),
        to='vanotify@va.gov',
    )
    resp = client.post('v2/notifications', json=request.serialize())
    assert resp.status_code == status.HTTP_201_CREATED
    assert isinstance(V2NotificationSingleResponse.model_validate(resp.json()), V2NotificationSingleResponse)


def test_post_malformed_request(client: TestClient) -> None:
    """Test POST /v2/notifications/ with a malformed (empty) request.

    Args:
        client(TestClient): FastAPI client fixture

    """
    request: dict[str, str] = {}
    resp = client.post('v2/notifications', data=request)
    resp_text = resp.text

    # Response status code is correct
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    # Standard message is used
    assert RESPONSE_400 in resp_text


@pytest.mark.asyncio
@patch('app.providers.provider_aws.get_session', new_callable=AsyncMock)
@patch('app.legacy.v2.notifications.rest.get_arn_from_icn', new_callable=AsyncMock)
class TestNotificationsPush:
    """Test POST /v2/notifications/."""

    async def test_post_push_notifications_returns_201(
        self,
        mock_get_arn_from_icn: AsyncMock,
        mock_get_session: AsyncMock,
        client: TestClient,
    ) -> None:
        """Test route can return 201.

        Args:
            mock_get_arn_from_icn(AsyncMock): Mock return from Vetext to get ARN from ICN
            mock_get_session(AsyncMock): Mock call to AWS
            client(TestClient): FastAPI client fixture

        """
        # Mock the ARN return value
        mock_get_arn_from_icn.return_value = 'sample_arn_value'

        mock_client = AsyncMock()
        mock_client.publish.return_value = {'MessageId': 'message_id', 'SequenceNumber': '12345'}

        mock_session = AsyncMock()
        mock_session.create_client.return_value.__aenter__.return_value = mock_client
        mock_get_session.return_value = mock_session

        request = V2NotificationPushRequest(
            mobile_app=MobileAppType.VA_FLAGSHIP_APP,
            template_id='1',
            recipient_identifier='99999',
            personalization={'name': 'John'},
        )

        response = client.post('/v2/notifications', json=request.serialize())

        assert response.status_code == status.HTTP_201_CREATED
