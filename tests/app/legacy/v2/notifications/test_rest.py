"""Test module for app/legacy/v2/notifications/rest.py."""

from typing import ClassVar
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import BackgroundTasks, status
from fastapi.encoders import jsonable_encoder
from starlette_context import request_cycle_context

from app.constants import IdentifierType, MobileAppType
from app.legacy.v2.notifications.rest import (
    _create_notification_record,
    _handle_direct_sms_notification,
    _handle_identifier_sms_notification,
    _lookup_contact_info,
    get_sms_notification_handler,
)
from app.legacy.v2.notifications.route_schema import (
    RecipientIdentifierModel,
    V2PostPushRequestModel,
    V2PostPushResponseModel,
    V2PostSmsRequestModel,
    ValidatedPhoneNumber,
)
from tests.conftest import ENPTestClient

_push_path = '/legacy/v2/notifications/push'


@patch.object(BackgroundTasks, 'add_task')
class TestPushRouter:
    """Test the v2 push notifications router."""

    async def test_router_returns_400_with_invalid_request_data(
        self,
        mock_background_task: AsyncMock,
        client: ENPTestClient,
    ) -> None:
        """Test route can return 400.

        Args:
            mock_background_task (AsyncMock): Mock call to add a background task
            client (ENPTestClient): Custom FastAPI client fixture

        """
        invalid_request = {
            'mobile_app': 'fake_app',
            'template_id': 'not_a_uuid',
            'recipient_identifier': {
                'id_type': 'not_ICN',
                'id_value': r'¯\_(ツ)_/¯',
            },
            'personalisation': 'not_a_dict',
        }

        response = client.post(_push_path, json=invalid_request)

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@patch.object(BackgroundTasks, 'add_task')
class TestPush:
    """Test POST /legacy/v2/notifications/push."""

    async def test_post_push_returns_201(
        self,
        mock_background_task: AsyncMock,
        client: ENPTestClient,
    ) -> None:
        """Test route can return 201.

        Args:
            mock_background_task (AsyncMock): Mock call to add a background task
            client (ENPTestClient): Custom FastAPI client fixture

        """
        request = V2PostPushRequestModel(
            mobile_app=MobileAppType.VA_FLAGSHIP_APP,
            template_id='d5b6e67c-8e2a-11ee-8b8e-0242ac120002',
            recipient_identifier=V2PostPushRequestModel.ICNRecipientIdentifierModel(
                id_type=IdentifierType.ICN,
                id_value='12345',
            ),
            personalisation={'name': 'John'},
        )

        response = client.post(_push_path, json=request.model_dump())

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json() == {'result': 'success'} == V2PostPushResponseModel().model_dump()


class TestNotificationRouter:
    """Test the v2 notifications router."""

    routes = (
        '/legacy/v2/notifications/sms',
        '/v2/notifications/sms',
    )

    @pytest.mark.parametrize('route', routes)
    async def test_happy_path(
        self,
        client: ENPTestClient,
        route: str,
    ) -> None:
        """Test route can return 201.

        Args:
            client (ENPTestClient): Custom FastAPI client fixture
            route (str): Route to test

        """
        template_id = uuid4()
        sms_sender_id = uuid4()

        request = V2PostSmsRequestModel(
            reference=str(uuid4()),
            template_id=template_id,
            phone_number=ValidatedPhoneNumber('+18005550101'),
            sms_sender_id=sms_sender_id,
        )
        payload = jsonable_encoder(request)
        with patch('app.legacy.v2.notifications.rest.validate_template', return_value=None):
            response = client.post(route, json=payload)

        assert response.status_code == status.HTTP_201_CREATED

    @pytest.mark.parametrize('route', routes)
    async def test_router_returns_400_with_invalid_request_data(
        self,
        client: ENPTestClient,
        route: str,
    ) -> None:
        """Test route can return 400.

        Args:
            client (ENPTestClient): Custom FastAPI client fixture
            route (str): Route to test

        """
        response = client.post(route)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.parametrize('route', routes)
    async def test_auth_error_uses_v2_json_structure(
        self,
        client: ENPTestClient,
        route: str,
    ) -> None:
        """Test route can return 201.

        Args:
            client (ENPTestClient): Custom FastAPI client fixture
            route (str): Route to test

        """
        request = V2PostSmsRequestModel(
            reference=str(uuid4()),
            template_id=uuid4(),
            phone_number=ValidatedPhoneNumber('+18005550101'),
            sms_sender_id=uuid4(),
        )
        payload = jsonable_encoder(request)
        with patch('app.legacy.v2.notifications.rest.validate_template', return_value=None):
            response = client.post(route, json=payload, headers={'Authorization': ''})

        error_details = {
            'errors': [
                {
                    'error': 'AuthError',
                    'message': 'Unauthorized, authentication token must be provided',
                },
            ],
            'status_code': 401,
        }

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json() == error_details


@patch('app.legacy.v2.notifications.rest.validate_template', return_value=None)
class TestV2SMS:
    """Test the v2 SMS notifications router."""

    # Error details based on consistency with the flask api
    error_details: ClassVar = {
        'errors': [
            {
                'error': 'ValidationError',
                'message': '',
            },
        ],
        'status_code': 400,
    }

    sms_route = '/legacy/v2/notifications/sms'
    template_id = uuid4()
    sms_sender_id = uuid4()

    @pytest.fixture
    def sms_request_data(self) -> dict[str, str]:
        """Return valid request data."""
        request_data = V2PostSmsRequestModel(
            reference=str(uuid4()),
            template_id=self.template_id,
            phone_number=ValidatedPhoneNumber('+18005550101'),
            sms_sender_id=self.sms_sender_id,
        )
        data: dict[str, str] = jsonable_encoder(request_data)
        return data

    @pytest.fixture
    def sms_request_with_identifier_data(self) -> dict[str, str]:
        """Return valid request data with recipient identifier instead of phone number."""
        request_data = V2PostSmsRequestModel(
            reference=str(uuid4()),
            template_id=self.template_id,
            sms_sender_id=self.sms_sender_id,
            recipient_identifier=RecipientIdentifierModel(
                id_type=IdentifierType.ICN,
                id_value='1234567890V123456',  # Valid ICN format: 10 digits + 'V' + 6 digits
            ),
        )
        data: dict[str, str] = jsonable_encoder(request_data)
        return data

    async def test_v2_sms_returns_201(
        self,
        mock_validate_template: AsyncMock,
        client: ENPTestClient,
        sms_request_data: dict[str, str],
    ) -> None:
        """Test sms notification route returns 201 with valid template."""
        response = client.post(self.sms_route, json=sms_request_data)

        assert response.status_code == status.HTTP_201_CREATED

    async def test_v2_sms_with_recipient_identifier_returns_201(
        self,
        mock_validate_template: AsyncMock,
        client: ENPTestClient,
        sms_request_with_identifier_data: dict[str, str],
    ) -> None:
        """Test sms notification route returns 201 with valid recipient identifier."""
        response = client.post(self.sms_route, json=sms_request_with_identifier_data)

        assert response.status_code == status.HTTP_201_CREATED
        response_json = response.json()
        # Verify response has expected structure with ID and URI
        assert 'id' in response_json
        assert 'uri' in response_json

    async def test_sms_notification_handler_selection(
        self,
        mock_validate_template: AsyncMock,
    ) -> None:
        """Test the get_sms_notification_handler function selects the appropriate handler."""
        # Test with phone number
        request_with_phone = V2PostSmsRequestModel(
            reference=str(uuid4()),
            template_id=self.template_id,
            phone_number=ValidatedPhoneNumber('+18005550101'),
            sms_sender_id=self.sms_sender_id,
        )
        handler = get_sms_notification_handler(request_with_phone)
        assert handler == _handle_direct_sms_notification

        # Test with recipient identifier
        request_with_identifier = V2PostSmsRequestModel(
            reference=str(uuid4()),
            template_id=self.template_id,
            sms_sender_id=self.sms_sender_id,
            recipient_identifier=RecipientIdentifierModel(
                id_type=IdentifierType.ICN,
                id_value='1234567890V123456',  # Valid ICN format: 10 digits + 'V' + 6 digits
            ),
        )
        handler = get_sms_notification_handler(request_with_identifier)
        assert handler == _handle_identifier_sms_notification

    async def test_v2_sms_returns_400_with_invalid_template(
        self,
        mock_validate_template: AsyncMock,
        client: ENPTestClient,
        sms_request_data: dict[str, str],
    ) -> None:
        """Test route returns 400 with invalid template (wrong template type)."""
        error_details = self.error_details.copy()
        error_details['errors'][0]['message'] = 'email template is not suitable for sms notification'

        # class-level patch
        mock_validate_template.side_effect = ValueError(error_details['errors'][0]['message'])

        response = client.post(self.sms_route, json=sms_request_data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

        assert response.json() == error_details

    async def test_v2_sms_returns_400_with_invalid_personalisation(
        self,
        mock_validate_template: AsyncMock,
        client: ENPTestClient,
        sms_request_data: dict[str, str],
    ) -> None:
        """Test route returns 400 with invalid personalisation."""
        error_details = self.error_details.copy()
        error_details['errors'][0]['message'] = 'Missing personalisation: content'

        # class-level patch
        mock_validate_template.side_effect = ValueError(error_details['errors'][0]['message'])

        response = client.post(self.sms_route, json=sms_request_data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        response_json = response.json()
        assert len(response_json['errors']) == 1
        assert response_json['errors'][0]['message'] == 'Missing personalisation: content'

    async def test_v2_sms_returns_custom_uuid_message_for_invalid_uuid(
        self,
        mock_validate_template: AsyncMock,
        client: ENPTestClient,
        sms_request_data: dict[str, str],
    ) -> None:
        """Test route returns 400 and custom UUID formatting message."""
        sms_request_data['template_id'] = 'bad_uuid'
        expected_message = 'template_id: Input should be a valid UUID version 4'
        expected_response = {
            'errors': [
                {
                    'error': 'ValidationError',
                    'message': expected_message,
                },
            ],
            'status_code': 400,
        }

        response = client.post(self.sms_route, json=sms_request_data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == expected_response


@patch('app.legacy.v2.notifications.rest.get_contact_info')
class TestHandleIdentifierSmsNotification:
    """Test the _handle_identifier_sms_notification function."""

    @pytest.fixture
    def request_with_recipient_identifier(self) -> V2PostSmsRequestModel:
        """Return a V2PostSmsRequestModel with a recipient identifier."""
        return V2PostSmsRequestModel(
            reference=str(uuid4()),
            template_id=uuid4(),
            sms_sender_id=uuid4(),
            recipient_identifier=RecipientIdentifierModel(
                id_type=IdentifierType.ICN,
                id_value='1234567890V123456',
            ),
        )

    async def test_handle_with_none_phone_number(
        self,
        mock_get_contact_info: AsyncMock,
        request_with_recipient_identifier: V2PostSmsRequestModel,
    ) -> None:
        """Test _handle_identifier_sms_notification when phone_number is None but contact_info exists."""
        from starlette_context import request_cycle_context

        notification_id = uuid4()
        template_id = uuid4()
        template_version = 1

        # Return a contact_info dict with None phone_number
        mock_get_contact_info.return_value = {'phone_number': None, 'email': 'test@example.com'}

        # Create a proper request context
        with request_cycle_context(
            {'template_id': f'{template_id}:1', 'notification_id': notification_id, 'service_id': uuid4()}
        ):
            # Call the handler within the context
            result = await _handle_identifier_sms_notification(
                request_with_recipient_identifier, notification_id, template_id, template_version
            )

            # Assertions
            mock_get_contact_info.assert_called_once()
            # Check that the status is delivered
            assert result['status'] == 'delivered'
            # Check that phone_number is present and set to 'UNKNOWN'
            assert 'phone_number' in result
            assert result['phone_number'] == 'UNKNOWN'

    async def test_handle_with_empty_phone_number(
        self,
        mock_get_contact_info: AsyncMock,
        request_with_recipient_identifier: V2PostSmsRequestModel,
    ) -> None:
        """Test _handle_identifier_sms_notification when phone_number is empty string."""
        from starlette_context import request_cycle_context

        notification_id = uuid4()
        template_id = uuid4()
        template_version = 1

        # Return a contact_info dict with empty phone_number
        mock_get_contact_info.return_value = {'phone_number': '', 'email': 'test@example.com'}

        # Create a proper request context
        with request_cycle_context(
            {'template_id': f'{template_id}:1', 'notification_id': notification_id, 'service_id': uuid4()}
        ):
            # Call the handler within the context
            result = await _handle_identifier_sms_notification(
                request_with_recipient_identifier, notification_id, template_id, template_version
            )

            # Assert failure due to missing phone number (empty string is falsy)
            assert result['status'] == 'failed'
            assert result['reason'] == 'no_phone_number'
            # phone_number should not be present in this failure case
            assert 'phone_number' not in result

    async def test_handle_general_exception(
        self,
        mock_get_contact_info: AsyncMock,
        request_with_recipient_identifier: V2PostSmsRequestModel,
    ) -> None:
        """Test _handle_identifier_sms_notification when a general exception occurs."""
        notification_id = uuid4()
        template_id = uuid4()
        template_version = 1

        # Simulate a general exception during contact info lookup
        mock_get_contact_info.side_effect = Exception('Something went wrong')

        # Create a proper request context
        with request_cycle_context(
            {'template_id': f'{template_id}:1', 'notification_id': notification_id, 'service_id': uuid4()}
        ):
            # Call the handler within the context
            result = await _handle_identifier_sms_notification(
                request_with_recipient_identifier, notification_id, template_id, template_version
            )

            # Assertions
            mock_get_contact_info.assert_called_once()
            # Check that the status is failed
            assert result['status'] == 'failed'
            # Check that reason contains the exception message
            assert 'reason' in result
            assert 'lookup_error:' in result['reason']
            assert 'Something went wrong' in result['reason']
            # Verify the notification record contains the proper fields
            assert result['id'] == str(notification_id)
            assert result['template_id'] == str(template_id)
            assert result['template_version'] == str(template_version)
            assert 'timestamp' in result


@patch('app.legacy.v2.notifications.rest.get_contact_info')
class TestLookupContactInfo:
    """Test the _lookup_contact_info function."""

    async def test_successful_contact_info_lookup(self, mock_get_contact_info: AsyncMock) -> None:
        """Test successful contact information lookup."""
        mock_contact_info = {'phone_number': '+18005550101', 'email': 'test@example.com'}
        mock_get_contact_info.return_value = mock_contact_info

        result = await _lookup_contact_info('ICN', '1234567890V123456', 'MASKED_ID')

        mock_get_contact_info.assert_called_once_with('ICN', '1234567890V123456')
        assert result == mock_contact_info

    async def test_invalid_identifier_raises_value_error(self, mock_get_contact_info: AsyncMock) -> None:
        """Test value error is propagated when client raises it."""
        mock_get_contact_info.side_effect = ValueError('Invalid identifier format')

        with pytest.raises(ValueError, match='Invalid identifier format') as exc_info:
            await _lookup_contact_info('ICN', 'INVALID_ID', 'MASKED_ID')

        assert 'Invalid identifier format' in str(exc_info.value)
        mock_get_contact_info.assert_called_once()

    async def test_user_not_found_raises_key_error(self, mock_get_contact_info: AsyncMock) -> None:
        """Test key error is propagated when user is not found."""
        mock_get_contact_info.side_effect = KeyError('User not found')

        with pytest.raises(KeyError) as exc_info:
            await _lookup_contact_info('ICN', '1234567890V123456', 'MASKED_ID')

        # KeyError's args[0] contains the key that wasn't found
        assert 'User not found' == str(exc_info.value.args[0])
        mock_get_contact_info.assert_called_once()

    async def test_connection_error_is_propagated(self, mock_get_contact_info: AsyncMock) -> None:
        """Test that connection error is propagated."""
        mock_get_contact_info.side_effect = ConnectionError('Failed to connect to VA Profile')

        with pytest.raises(ConnectionError) as exc_info:
            await _lookup_contact_info('ICN', '1234567890V123456', 'MASKED_ID')

        assert 'Failed to connect to VA Profile' in str(exc_info.value)
        mock_get_contact_info.assert_called_once()

    async def test_unexpected_error_converts_to_connection_error(self, mock_get_contact_info: AsyncMock) -> None:
        """Test that unexpected exceptions are converted to ConnectionError."""
        mock_get_contact_info.side_effect = Exception('Unexpected error occurred')

        with pytest.raises(ConnectionError, match=r'Error connecting to VA Profile.*Unexpected error occurred'):
            await _lookup_contact_info('ICN', '1234567890V123456', 'MASKED_ID')

        mock_get_contact_info.assert_called_once()


class TestCreateNotificationRecord:
    """Test the _create_notification_record function."""

    def test_create_notification_record_basic(self) -> None:
        """Test _create_notification_record with basic required fields."""
        notification_id = uuid4()
        template_id = uuid4()
        template_version = 1
        recipient_id_type = 'ICN'
        masked_id = '1234567XXXXXX'
        status = 'delivered'

        record = _create_notification_record(
            notification_id,
            template_id,
            template_version,
            recipient_id_type,
            masked_id,
            status,
        )

        # Test basic fields
        assert record['id'] == str(notification_id)
        assert record['template_id'] == str(template_id)
        assert record['template_version'] == str(template_version)
        assert record['recipient_identifier_type'] == recipient_id_type
        assert record['recipient_identifier_value'] == masked_id
        assert record['status'] == status
        assert 'timestamp' in record

        # Ensure optional fields aren't included
        assert 'reason' not in record
        assert 'phone_number' not in record
        assert 'recipient' not in record

    def test_create_notification_record_with_reason(self) -> None:
        """Test _create_notification_record with reason field."""
        notification_id = uuid4()
        template_id = uuid4()
        reason = 'no_phone_number'

        record = _create_notification_record(
            notification_id, template_id, 1, 'ICN', '1234567XXXXXX', 'failed', reason=reason
        )

        assert record['reason'] == reason

    def test_create_notification_record_with_phone_number(self) -> None:
        """Test _create_notification_record with phone_number field."""
        notification_id = uuid4()
        template_id = uuid4()
        phone_number = '+1XXXXXXX1234'

        record = _create_notification_record(
            notification_id, template_id, 1, 'ICN', '1234567XXXXXX', 'delivered', phone_number=phone_number
        )

        assert record['phone_number'] == phone_number

    def test_create_notification_record_with_recipient(self) -> None:
        """Test _create_notification_record with recipient field."""
        notification_id = uuid4()
        template_id = uuid4()
        recipient = '+18005550101'

        record = _create_notification_record(
            notification_id, template_id, 1, 'ICN', '1234567XXXXXX', 'delivered', recipient=recipient
        )

        # This is the specific test for line 213
        assert record['recipient'] == recipient

    def test_create_notification_record_with_multiple_additional_fields(self) -> None:
        """Test _create_notification_record with all additional fields."""
        notification_id = uuid4()
        template_id = uuid4()

        record = _create_notification_record(
            notification_id,
            template_id,
            1,
            'ICN',
            '1234567XXXXXX',
            'delivered',
            reason='testing',
            phone_number='+1XXXXXXX5555',
            recipient='+18005550101',
        )

        # Verify all additional fields are present
        assert record['reason'] == 'testing'
        assert record['phone_number'] == '+1XXXXXXX5555'
        assert record['recipient'] == '+18005550101'

    def test_create_notification_record_with_none_values(self) -> None:
        """Test _create_notification_record with None values in additional fields."""
        notification_id = uuid4()
        template_id = uuid4()

        record = _create_notification_record(
            notification_id,
            template_id,
            1,
            'ICN',
            '1234567XXXXXX',
            'delivered',
            reason=None,
            phone_number=None,
            recipient=None,
        )

        # None values should not be included in the record
        assert 'reason' not in record
        assert 'phone_number' not in record
        assert 'recipient' not in record
