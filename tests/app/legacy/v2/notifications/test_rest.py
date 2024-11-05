"""Test module for app/legacy/v2/notifications/rest.py."""

from typing import Callable, Generator
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.constants import MobileAppType
from app.db.models import Template
from app.legacy.v2.notifications.route_schema import (
    V2NotificationPushRequest,
)
from app.providers.provider_base import ProviderNonRetryableError


@pytest.mark.asyncio
@patch('app.providers.provider_aws.get_session')
@patch('app.legacy.v2.notifications.rest.get_arn_from_icn', new_callable=AsyncMock)
class TestNotificationsPush:
    """Test POST /v2/notifications/."""

    async def test_post_push_notifications_returns_201(
        self,
        mock_get_arn_from_icn: AsyncMock,
        mock_get_session: AsyncMock,
        sample_template: Generator[Callable[[str], Template], None, None],
        client: TestClient,
    ) -> None:
        """Test route can return 201.

        Args:
            mock_get_arn_from_icn(AsyncMock): Mock return from VAProfile to get ARN from ICN
            mock_get_session(AsyncMock): Mock call to AWS
            sample_template(Generator[Callable[[str], Template], None, None]): Function to create sample templates
            client(TestClient): FastAPI client fixture

        """
        await sample_template(name='test_template')
        mock_get_arn_from_icn.return_value = 'sample_arn_value'

        mock_client = AsyncMock()
        mock_client.publish.return_value = {'MessageId': 'message_id', 'SequenceNumber': '12345'}
        mock_get_session.return_value.create_client.return_value.__aenter__.return_value = mock_client

        request = V2NotificationPushRequest(
            mobile_app=MobileAppType.VA_FLAGSHIP_APP,
            template_id='d5b6e67c-8e2a-11ee-8b8e-0242ac120002',
            recipient_identifier='99999',
            personalization={'name': 'John'},
        )

        response = client.post('/v2/notifications', json=request.model_dump())

        assert response.status_code == status.HTTP_201_CREATED

    async def test_post_push_notifications_without_personalization(
        self,
        mock_get_arn_from_icn: AsyncMock,
        mock_get_session: AsyncMock,
        client: TestClient,
    ) -> None:
        """Test route can return 201 without personalization field.

        Args:
            mock_get_arn_from_icn(AsyncMock): Mock return from Vetext to get ARN from ICN
            mock_get_session(AsyncMock): Mock call to AWS
            client(TestClient): FastAPI client fixture

        """
        mock_get_arn_from_icn.return_value = 'sample_arn_value'

        mock_client = AsyncMock()
        mock_client.publish.return_value = {'MessageId': 'message_id', 'SequenceNumber': '12345'}
        mock_get_session.return_value.create_client.return_value.__aenter__.return_value = mock_client

        request = V2NotificationPushRequest(
            mobile_app=MobileAppType.VA_FLAGSHIP_APP,
            template_id='d5b6e67c-8e2a-11ee-8b8e-0242ac120002',
            recipient_identifier='99999',
        )

        response = client.post('/v2/notifications', json=request.model_dump())

        assert response.status_code == status.HTTP_201_CREATED

    @pytest.mark.parametrize(
        ('missing_field', 'request_data'),
        [
            (
                'template_id',
                {
                    'mobile_app': MobileAppType.VA_FLAGSHIP_APP,
                    'recipient_identifier': '99999',
                    'personalization': {'name': 'John'},
                },
            ),
            (
                'recipient_identifier',
                {
                    'mobile_app': MobileAppType.VA_FLAGSHIP_APP,
                    'template_id': '1',
                    'personalization': {'name': 'John'},
                },
            ),
            (
                'mobile_app',
                {
                    'template_id': '1',
                    'recipient_identifier': '99999',
                    'personalization': {'name': 'John'},
                },
            ),
        ],
        ids=(
            'Missing template_id',
            'Missing recipient_identifier',
            'Missing mobile_app',
        ),
    )
    async def test_post_push_notifications_missing_required_field(
        self,
        mock_get_arn_from_icn: AsyncMock,
        mock_get_session: AsyncMock,
        client: TestClient,
        missing_field: str,
        request_data: dict[str, str],
    ) -> None:
        """Test route returns 400 when required fields are missing.

        Args:
            mock_get_arn_from_icn(AsyncMock): Mock return from Vetext to get ARN from ICN
            mock_get_session(AsyncMock): Mock call to AWS
            client(TestClient): FastAPI client fixture
            missing_field(str): The field that is missing from the request data
            request_data(dict): The incomplete request data

        """
        response = client.post('/v2/notifications', json=request_data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert missing_field in response.text

    async def test_post_template_not_found(
        self,
        mock_get_arn_from_icn: AsyncMock,
        mock_get_session: AsyncMock,
        client: TestClient,
    ) -> None:
        """Test route returns 400 when the template is not found.

        Args:
            mock_get_arn_from_icn(AsyncMock): Mock return from Vetext to get ARN from ICN
            mock_get_session(AsyncMock): Mock call to AWS
            client(TestClient): FastAPI client fixture

        """
        mock_get_arn_from_icn.return_value = 'sample_arn_value'

        request = V2NotificationPushRequest(
            mobile_app=MobileAppType.VA_FLAGSHIP_APP,
            template_id='1234',
            recipient_identifier='99999',
            personalization={'name': 'John'},
        )

        response = client.post('/v2/notifications', json=request.model_dump())

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.text == 'Template with template_id 1234 not found.'

    async def test_post_push_notification_failure_returns_500(
        self,
        mock_get_arn_from_icn: AsyncMock,
        mock_get_session: AsyncMock,
        client: TestClient,
    ) -> None:
        """Test route returns 500 when sending notification fails.

        Args:
            mock_get_arn_from_icn(AsyncMock): Mock return from Vetext to get ARN from ICN
            mock_get_session(AsyncMock): Mock call to AWS
            client(TestClient): FastAPI client fixture

        """
        mock_get_arn_from_icn.return_value = 'sample_arn_value'

        mock_client = AsyncMock()
        mock_client.publish.side_effect = ProviderNonRetryableError()
        mock_get_session.return_value.create_client.return_value.__aenter__.return_value = mock_client

        request = V2NotificationPushRequest(
            mobile_app=MobileAppType.VA_FLAGSHIP_APP,
            template_id='d5b6e67c-8e2a-11ee-8b8e-0242ac120002',
            recipient_identifier='99999',
            personalization={'name': 'John'},
        )

        response = client.post('/v2/notifications', json=request.model_dump())

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response.text == 'Internal error. Failed to create notification.'
