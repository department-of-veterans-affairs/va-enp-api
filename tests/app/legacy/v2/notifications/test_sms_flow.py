"""Test module for the SMS notification flow."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import status

from app.constants import IdentifierType, NotificationType
from tests.conftest import ENPTestClient


@patch('app.legacy.v2.notifications.rest.validate_template')
class TestSmsFlow:
    """Test the SMS notification flow implementation."""

    sms_route = '/legacy/v2/notifications/sms'

    @pytest.fixture
    def template_content(self) -> str:
        """Return mock template content."""
        return 'Hello, this is a test message with personalization: {name}.'

    @patch('app.legacy.dao.notifications_dao.LegacyNotificationDao.persist_notification')
    @patch('app.legacy.v2.notifications.process_notifications.send_notification_to_queue')
    async def test_direct_sms_flow(
        self,
        mock_send_queue: AsyncMock,
        mock_persist: AsyncMock,
        mock_validate_template: AsyncMock,
        client: ENPTestClient,
        template_content: str,
    ) -> None:
        """Test the direct SMS flow with a phone number."""
        # Setup mocks
        mock_validate_template.return_value = template_content
        notification_id = uuid4()
        mock_persist.return_value = {
            'id': notification_id,
            'notification_type': NotificationType.SMS,
            'status': 'created',
        }

        # Create test request data
        template_id = uuid4()
        request_data = {
            'template_id': str(template_id),
            'phone_number': '+18005551234',
            'personalisation': {'name': 'Test User', 'appointment_date': '2023-04-15'},
            'reference': 'test-ref-123',
        }

        # Execute request
        response = client.post(self.sms_route, json=request_data)

        # Assert response
        assert response.status_code == status.HTTP_201_CREATED
        response_data = response.json()
        assert response_data['reference'] == 'test-ref-123'
        assert 'content' in response_data
        assert 'body' in response_data['content']

        # Verify persistence was called
        mock_persist.assert_called_once()
        persist_kwargs = mock_persist.call_args.kwargs
        assert persist_kwargs['recipient'] == '+18005551234'
        assert persist_kwargs['template_id'] == template_id
        assert persist_kwargs['notification_type'] == NotificationType.SMS

        # Verify queue was called
        mock_send_queue.assert_called_once()

    @patch('app.legacy.dao.notifications_dao.LegacyNotificationDao.persist_notification')
    @patch(
        'app.legacy.v2.notifications.process_notifications.send_to_queue_for_recipient_info_based_on_recipient_identifier'
    )
    async def test_recipient_identifier_flow(
        self,
        mock_send_queue: AsyncMock,
        mock_persist: AsyncMock,
        mock_validate_template: AsyncMock,
        client: ENPTestClient,
        template_content: str,
    ) -> None:
        """Test the SMS flow with a recipient identifier."""
        # Setup mocks
        mock_validate_template.return_value = template_content
        notification_id = uuid4()
        mock_persist.return_value = {
            'id': notification_id,
            'notification_type': NotificationType.SMS,
            'status': 'created',
        }

        # Create test request data
        template_id = uuid4()
        icn_value = '1234567890V123456'
        request_data = {
            'template_id': str(template_id),
            'recipient_identifier': {'id_type': IdentifierType.ICN, 'id_value': icn_value},
            'personalisation': {'name': 'Test User', 'appointment_date': '2023-04-15'},
        }

        # Execute request
        response = client.post(self.sms_route, json=request_data)

        # Assert response
        assert response.status_code == status.HTTP_201_CREATED
        response_data = response.json()
        assert 'id' in response_data
        assert 'content' in response_data
        assert 'body' in response_data['content']

        # Verify persistence was called with recipient identifier
        mock_persist.assert_called_once()
        persist_kwargs = mock_persist.call_args.kwargs
        assert persist_kwargs['recipient'] is None
        assert 'recipient_identifier' in persist_kwargs
        assert persist_kwargs['recipient_identifier']['id_type'] == IdentifierType.ICN
        assert persist_kwargs['recipient_identifier']['id_value'] == icn_value

        # Verify recipient lookup queue was called
        mock_send_queue.assert_called_once()
        queue_kwargs = mock_send_queue.call_args.kwargs
        assert queue_kwargs['id_type'] == IdentifierType.ICN
        assert queue_kwargs['id_value'] == icn_value
