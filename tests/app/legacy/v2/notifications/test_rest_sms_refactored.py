"""Test module for refactored SMS notification route handler in app/legacy/v2/notifications/rest.py."""

from typing import Generator
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import status
from fastapi.encoders import jsonable_encoder

from app.constants import IdentifierType, NotificationType
from app.legacy.v2.notifications.route_schema import (
    RecipientIdentifierModel,
    V2PostSmsRequestModel,
    ValidatedPhoneNumber,
)
from app.legacy.v2.notifications.services.interfaces import SmsProcessor
from tests.conftest import ENPTestClient


class TestRefactoredSmsRouteHandler:
    """Tests for the refactored SMS notification route handler."""

    sms_routes = (
        '/legacy/v2/notifications/sms',
        '/v2/notifications/sms',
    )
    template_id = uuid4()
    sms_sender_id = uuid4()

    @pytest.fixture
    def sms_phone_request(self) -> dict:
        """Return valid SMS request data with phone number.

        Returns:
            dict: Request data
        """
        request_data = V2PostSmsRequestModel(
            reference=str(uuid4()),
            template_id=self.template_id,
            phone_number=ValidatedPhoneNumber('+18005550101'),
            sms_sender_id=self.sms_sender_id,
        )
        return jsonable_encoder(request_data)

    @pytest.fixture
    def sms_recipient_id_request(self) -> dict:
        """Return valid SMS request data with recipient identifier.

        Returns:
            dict: Request data
        """
        request_data = V2PostSmsRequestModel(
            reference=str(uuid4()),
            template_id=self.template_id,
            recipient_identifier=RecipientIdentifierModel(id_type=IdentifierType.ICN, id_value='1234567890V123456'),
            sms_sender_id=self.sms_sender_id,
        )
        return jsonable_encoder(request_data)

    @pytest.fixture
    def sms_both_identifiers_request(self) -> dict:
        """Return valid SMS request data with both phone number and recipient identifier.

        Returns:
            dict: Request data
        """
        request_data = V2PostSmsRequestModel(
            reference=str(uuid4()),
            template_id=self.template_id,
            phone_number=ValidatedPhoneNumber('+18005550101'),
            recipient_identifier=RecipientIdentifierModel(id_type=IdentifierType.ICN, id_value='1234567890V123456'),
            sms_sender_id=self.sms_sender_id,
        )
        return jsonable_encoder(request_data)

    @pytest.fixture
    def mock_sms_processor(self) -> AsyncMock:
        """Create a mock SmsProcessor with a process method.

        Returns:
            AsyncMock: A mock SmsProcessor instance with process method.
        """
        processor = AsyncMock(spec=SmsProcessor)
        processor.process = AsyncMock()
        return processor

    @pytest.fixture
    def setup_dependencies(self, client: ENPTestClient, mock_sms_processor: AsyncMock) -> Generator[None, None, None]:
        """Setup FastAPI dependency overrides for testing.

        Args:
            client: The test client
            mock_sms_processor: The mock SmsProcessor to use

        Yields:
            None: This fixture yields control back to the test.
        """
        # Store original overrides to restore later
        original_overrides = client.app.dependency_overrides.copy()

        # Override the get_sms_processor dependency
        # We need to use the actual function object as the key, not a string
        from app.legacy.v2.notifications.services.providers import get_sms_processor

        client.app.dependency_overrides[get_sms_processor] = lambda: mock_sms_processor

        yield

        # Restore original overrides after test
        client.app.dependency_overrides = original_overrides

    @pytest.mark.parametrize('route', sms_routes)
    @patch('app.legacy.v2.notifications.rest.validate_template')
    async def test_sms_with_phone_number(
        self,
        mock_validate_template: AsyncMock,
        mock_sms_processor: AsyncMock,
        setup_dependencies: None,
        client: ENPTestClient,
        route: str,
        sms_phone_request: dict,
    ) -> None:
        """Test SMS notification with phone number.

        Args:
            mock_validate_template: Mock for validate_template function
            mock_sms_processor: Mock SmsProcessor fixture
            setup_dependencies: Fixture to setup dependency overrides
            client: Test client
            route: Route to test
            sms_phone_request: Request data with phone number
        """
        # Arrange
        mock_validate_template.return_value = None
        mock_sms_processor.process.return_value = None

        # Act
        response = client.post(route, json=sms_phone_request)

        # Assert
        assert response.status_code == status.HTTP_201_CREATED
        mock_validate_template.assert_called_once_with(self.template_id, NotificationType.SMS, None)
        mock_sms_processor.process.assert_called_once()
        # Verify phone number was passed as a kwarg
        assert 'phone_number' in mock_sms_processor.process.call_args.kwargs
        assert mock_sms_processor.process.call_args.kwargs['phone_number'] == '+18005550101'

    @pytest.mark.parametrize('route', sms_routes)
    @patch('app.legacy.v2.notifications.rest.validate_template')
    async def test_sms_with_recipient_identifier(
        self,
        mock_validate_template: AsyncMock,
        mock_sms_processor: AsyncMock,
        setup_dependencies: None,
        client: ENPTestClient,
        route: str,
        sms_recipient_id_request: dict,
    ) -> None:
        """Test SMS notification with recipient identifier.

        Args:
            mock_validate_template: Mock for validate_template function
            mock_sms_processor: Mock SmsProcessor fixture
            setup_dependencies: Fixture to setup dependency overrides
            client: Test client
            route: Route to test
            sms_recipient_id_request: Request data with recipient identifier
        """
        # Arrange
        mock_validate_template.return_value = None
        mock_sms_processor.process.return_value = None

        # Act
        response = client.post(route, json=sms_recipient_id_request)

        # Assert
        assert response.status_code == status.HTTP_201_CREATED
        mock_validate_template.assert_called_once_with(self.template_id, NotificationType.SMS, None)
        mock_sms_processor.process.assert_called_once()
        # Verify recipient_identifier was passed as a kwarg
        assert 'recipient_identifier' in mock_sms_processor.process.call_args.kwargs
        assert mock_sms_processor.process.call_args.kwargs['recipient_identifier'].id_type == IdentifierType.ICN
        assert mock_sms_processor.process.call_args.kwargs['recipient_identifier'].id_value == '1234567890V123456'

    @pytest.mark.parametrize('route', sms_routes)
    @patch('app.legacy.v2.notifications.rest.validate_template')
    async def test_sms_with_both_identifiers(
        self,
        mock_validate_template: AsyncMock,
        mock_sms_processor: AsyncMock,
        setup_dependencies: None,
        client: ENPTestClient,
        route: str,
        sms_both_identifiers_request: dict,
    ) -> None:
        """Test SMS notification with both phone number and recipient identifier.

        Args:
            mock_validate_template: Mock for validate_template function
            mock_sms_processor: Mock SmsProcessor fixture
            setup_dependencies: Fixture to setup dependency overrides
            client: Test client
            route: Route to test
            sms_both_identifiers_request: Request data with both identifiers
        """
        # Arrange
        mock_validate_template.return_value = None
        mock_sms_processor.process.return_value = None

        # Act
        response = client.post(route, json=sms_both_identifiers_request)

        # Assert
        assert response.status_code == status.HTTP_201_CREATED
        mock_validate_template.assert_called_once_with(self.template_id, NotificationType.SMS, None)
        mock_sms_processor.process.assert_called_once()
        # Verify both identifiers were passed as kwargs
        assert 'phone_number' in mock_sms_processor.process.call_args.kwargs
        assert 'recipient_identifier' in mock_sms_processor.process.call_args.kwargs

    @pytest.mark.parametrize('route', sms_routes)
    @patch('app.legacy.v2.notifications.rest.validate_template')
    async def test_sms_with_processor_error(
        self,
        mock_validate_template: AsyncMock,
        mock_sms_processor: AsyncMock,
        setup_dependencies: None,
        client: ENPTestClient,
        route: str,
        sms_phone_request: dict,
    ) -> None:
        """Test SMS notification when processor raises an error.

        Args:
            mock_validate_template: Mock for validate_template function
            mock_sms_processor: Mock SmsProcessor fixture
            setup_dependencies: Fixture to setup dependency overrides
            client: Test client
            route: Route to test
            sms_phone_request: Request data
        """
        # Arrange
        mock_validate_template.return_value = None
        mock_sms_processor.process.side_effect = ValueError('Test error')

        # Act & Assert
        with pytest.raises(ValueError, match='Test error'):
            # This will raise an exception, which we're testing for
            client.post(route, json=sms_phone_request)

        # Verify the mock was actually called before the exception
        mock_sms_processor.process.assert_called_once()

    @pytest.mark.parametrize('route', sms_routes)
    @patch('app.legacy.v2.notifications.rest.validate_template', side_effect=ValueError('Invalid template'))
    async def test_template_validation_error(
        self,
        mock_validate_template: AsyncMock,
        client: ENPTestClient,
        route: str,
        sms_phone_request: dict,
    ) -> None:
        """Test SMS notification with template validation error.

        Args:
            mock_validate_template: Mock for validate_template function
            client: Test client
            route: Route to test
            sms_phone_request: Request data
        """
        # Act
        response = client.post(route, json=sms_phone_request)

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        error_details = response.json()
        assert 'errors' in error_details
        assert len(error_details['errors']) == 1
        assert error_details['errors'][0]['error'] == 'ValidationError'
        assert error_details['errors'][0]['message'] == 'Invalid template'
