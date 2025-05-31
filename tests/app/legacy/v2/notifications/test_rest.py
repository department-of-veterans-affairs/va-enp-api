"""Test module for app/legacy/v2/notifications/rest.py."""

import time
from typing import Any, Awaitable, Callable, ClassVar
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import BackgroundTasks, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy import Row

from app.auth import ACCESS_TOKEN_EXPIRE_SECONDS, JWTPayloadDict
from app.constants import IdentifierType, MobileAppType
from app.legacy.v2.notifications.resolvers import (
    DirectSmsTaskResolver,
    IdentifierSmsTaskResolver,
    get_sms_task_resolver,
)
from app.legacy.v2.notifications.route_schema import (
    RecipientIdentifierModel,
    V2PostPushRequestModel,
    V2PostPushResponseModel,
    V2PostSmsRequestModel,
    ValidatedPhoneNumber,
)
from tests.app.legacy.dao.test_api_keys import encode_and_sign
from tests.conftest import ENPTestClient, generate_token

_push_path = '/legacy/v2/notifications/push'


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
    async def test_happy_path_admin_auth(
        self,
        mock_background_task: AsyncMock,
        client: ENPTestClient,
        route: str,
    ) -> None:
        """Test route can return 201.

        Args:
            mock_background_task (AsyncMock): Mock call to add a background task
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
    async def test_happy_path_service_auth(
        self,
        mock_background_task: AsyncMock,
        sample_api_key: Callable[..., Awaitable[Row[Any]]],
        sample_service: Callable[..., Awaitable[Row[Any]]],
        client_factory: Callable[[str], ENPTestClient],
        route: str,
    ) -> None:
        """Should return 201 when request is authenticated with a valid service token.

        Args:
            mock_background_task (AsyncMock): Mock call to add a background task.
            sample_api_key (Callable): Fixture to create a sample API key.
            sample_service (Callable): Fixture to create a sample service.
            client_factory (Callable): Factory to create an ENPTestClient with a token.
            route (str): Route to test.
        """
        template_id = uuid4()
        sms_sender_id = uuid4()

        request = V2PostSmsRequestModel(
            reference=str(uuid4()),
            template_id=template_id,
            phone_number=ValidatedPhoneNumber('+18005550101'),
            sms_sender_id=sms_sender_id,
        )
        request_payload = jsonable_encoder(request)

        service = await sample_service()

        secret = 'not_so_secret'
        encrypted_secret = encode_and_sign(secret)
        api_key = await sample_api_key(service_id=service.id, secret=encrypted_secret)

        current_timestamp = int(time.time())
        payload: JWTPayloadDict = {
            'iss': str(service.id),
            'iat': current_timestamp,
            'exp': current_timestamp + 60,
        }
        token = generate_token(sig_key=secret, payload=payload)
        client = client_factory(token)

        with (
            patch('app.auth.LegacyServiceDao.get_service', new=AsyncMock(return_value=service)),
            patch('app.auth.LegacyApiKeysDao.get_api_keys', new=AsyncMock(return_value=[api_key])),
            patch('app.legacy.v2.notifications.rest.validate_template', return_value=None),
        ):
            response = client.post(route, json=request_payload)

        assert response.status_code == status.HTTP_201_CREATED

    @pytest.mark.parametrize('route', routes)
    async def test_router_returns_403_wrong_admin_secret(
        self,
        client_factory: Callable[[str], ENPTestClient],
        route: str,
    ) -> None:
        """Test sms notification route returns 403 with wrong admin secret."""
        payload = JWTPayloadDict(
            iss='enp',
            iat=int(time.time()),
            exp=int(time.time()) + ACCESS_TOKEN_EXPIRE_SECONDS,
        )
        token = generate_token(sig_key='not_the_admin_secret', payload=payload)
        client = client_factory(token)

        response = client.post(route)

        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.parametrize('route', routes)
    async def test_router_returns_401_missing_credentials(
        self,
        client: ENPTestClient,
        route: str,
        mocker: AsyncMock,
    ) -> None:
        """Test sms notification route returns 401 with missing credentials."""
        mocker.patch('app.auth.HTTPBearer.__call__', return_value=None)
        response = client.post(route)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

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


@patch('app.legacy.v2.notifications.rest.validate_template')
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
    def sms_request_data(self) -> dict[str, object]:
        """Return valid request data."""
        request_data = V2PostSmsRequestModel(
            reference=str(uuid4()),
            template_id=self.template_id,
            phone_number=ValidatedPhoneNumber('+18005550101'),
            sms_sender_id=self.sms_sender_id,
        )
        data: dict[str, object] = jsonable_encoder(request_data)
        return data

    @patch.object(BackgroundTasks, 'add_task')
    async def test_v2_sms_with_phone_number_returns_201(
        self,
        mock_background_task: AsyncMock,
        mock_validate_template: AsyncMock,
        service_authorized_client: ENPTestClient,
        sms_request_data: dict[str, object],
    ) -> None:
        """Test sms notification route returns 201 with valid template."""
        response = service_authorized_client.post(self.sms_route, json=sms_request_data)

        assert response.status_code == status.HTTP_201_CREATED

        # Verify response content structure and values
        response_data = response.json()
        assert 'id' in response_data
        assert 'template' in response_data
        assert 'content' in response_data
        assert 'uri' in response_data

        # Check that UUID fields are valid UUIDs
        UUID(response_data['id'])  # This will raise an exception if invalid

        # Check request fields are reflected in response
        assert response_data['reference'] == sms_request_data['reference']
        assert response_data['template']['id'] == str(self.template_id)

        # Check content structure
        assert 'body' in response_data['content']
        assert 'from_number' in response_data['content']
        assert response_data['content']['from_number'] == '+18005550101'

    @patch.object(BackgroundTasks, 'add_task')
    async def test_v2_sms_with_recipient_identifier_returns_201(
        self,
        mock_background_task: AsyncMock,
        mock_validate_template: AsyncMock,
        client: ENPTestClient,
        sms_request_data: dict[str, object],
    ) -> None:
        """Test sms notification route returns 201 with valid recipient identifier."""
        # Modify the request data to use recipient_identifier instead of phone_number
        sms_request_data.pop('phone_number', None)
        sms_request_data['recipient_identifier'] = {
            'id_type': IdentifierType.ICN,
            'id_value': '1234567890V123456',  # Valid ICN format: 10 digits + 'V' + 6 digits
        }

        response = client.post(self.sms_route, json=sms_request_data)

        assert response.status_code == status.HTTP_201_CREATED

        # Verify response content structure and values
        response_data = response.json()
        assert 'id' in response_data
        assert 'template' in response_data
        assert 'content' in response_data
        assert 'uri' in response_data

        # Check that response contains expected UUIDs and values
        UUID(response_data['id'])  # This will raise an exception if invalid
        assert response_data['reference'] == sms_request_data['reference']
        assert response_data['template']['id'] == str(self.template_id)
        assert response_data['template']['uri'].startswith('https://mock-notify.va.gov/templates/')
        assert response_data['uri'].startswith('https://mock-notify.va.gov/notifications/')

        # Check the content structure specific to SMS responses
        assert 'body' in response_data['content']
        assert 'from_number' in response_data['content']
        assert response_data['content']['from_number'] == '+18005550101'

        # Verify optional fields are handled correctly if present in request
        if 'billing_code' in sms_request_data:
            assert response_data['billing_code'] == sms_request_data['billing_code']
        if 'callback_url' in sms_request_data:
            assert response_data['callback_url'] == sms_request_data['callback_url']

    @patch.object(BackgroundTasks, 'add_task')
    async def test_sms_task_resolver_selection(
        self,
        mock_background_task: AsyncMock,
        mock_validate_template: AsyncMock,
    ) -> None:
        """Test the get_sms_task_resolver function selects the appropriate resolver."""
        # Setup
        mock_validate_template.return_value = None

        # Test direct phone number
        request_with_phone = V2PostSmsRequestModel(
            template_id=UUID('a71400e3-b2f8-4bd1-91c0-27f9ca7106a1'),
            phone_number='+18005550101',
        )
        resolver = get_sms_task_resolver(request_with_phone)
        assert isinstance(resolver, DirectSmsTaskResolver)
        assert resolver.phone_number == '+18005550101'

        # Test with recipient identifier
        request_with_identifier = V2PostSmsRequestModel(
            template_id=UUID('a71400e3-b2f8-4bd1-91c0-27f9ca7106a1'),
            recipient_identifier=RecipientIdentifierModel(
                id_type=IdentifierType.ICN,
                id_value='1234567890V123456',  # Valid ICN format: 10 digits + 'V' + 6 digits
            ),
        )
        resolver = get_sms_task_resolver(request_with_identifier)

        assert isinstance(resolver, IdentifierSmsTaskResolver)
        assert request_with_identifier.recipient_identifier is not None
        # Check that the id_type and id_value are correctly set in the resolver
        assert resolver.id_type == IdentifierType.ICN
        assert resolver.id_value == '1234567890V123456'

    async def test_v2_sms_returns_400_with_invalid_template(
        self,
        mock_validate_template: AsyncMock,
        client: ENPTestClient,
        sms_request_data: dict[str, object],
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
        sms_request_data: dict[str, object],
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
        sms_request_data: dict[str, object],
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

    async def test_v2_sms_prevents_duplicate_validation_errors(
        self,
        mock_validate_template: AsyncMock,
        client: ENPTestClient,
        sms_request_data: dict[str, object],
    ) -> None:
        """Test that we don't get duplicate validation errors when the same model is used twice.

        This test validates the fix for the issue described in this FastAPI issue, https://github.com/fastapi/fastapi/issues/4072.
        The underlying problem may be in passing the same request model to a route handler and a dependency resolver, resulting
        in duplicate validation.
        """
        # Modify the request data to have an invalid UUID for template_id
        sms_request_data['template_id'] = 'not-a-valid-uuid'

        # The route handler uses the model both directly and in the get_sms_task_resolver dependency
        response = client.post(self.sms_route, json=sms_request_data)

        # Check that we get a 400 error as expected
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        # Verify that the error message appears only once in the response
        response_json = response.json()
        assert len(response_json['errors']) == 1

        # The message should be formatted as described in the request_validation_error_handler
        assert response_json['errors'][0]['message'] == 'template_id: Input should be a valid UUID version 4'

        # Verify the status code is included in the response body
        assert response_json['status_code'] == 400
