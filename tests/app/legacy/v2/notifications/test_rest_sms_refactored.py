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
from app.legacy.v2.notifications.services.interfaces import PhoneNumberSmsProcessor, RecipientIdentifierSmsProcessor
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
    def mock_phone_processor(self) -> AsyncMock:
        """Create a mock PhoneNumberSmsProcessor with a process method.

        Returns:
            AsyncMock: A mock PhoneNumberSmsProcessor instance with process method.
        """
        processor = AsyncMock(spec=PhoneNumberSmsProcessor)
        processor.process = AsyncMock()
        return processor

    @pytest.fixture
    def mock_recipient_processor(self) -> AsyncMock:
        """Create a mock RecipientIdentifierSmsProcessor with a process method.

        Returns:
            AsyncMock: A mock RecipientIdentifierSmsProcessor instance with process method.
        """
        processor = AsyncMock(spec=RecipientIdentifierSmsProcessor)
        processor.process = AsyncMock()
        return processor

    @pytest.fixture
    def setup_dependencies(
        self, client: ENPTestClient, mock_phone_processor: AsyncMock, mock_recipient_processor: AsyncMock
    ) -> Generator[None, None, None]:
        """Setup FastAPI dependency overrides for testing.

        Args:
            client: The test client
            mock_phone_processor: The mock PhoneNumberSmsProcessor to use
            mock_recipient_processor: The mock RecipientIdentifierSmsProcessor to use

        Yields:
            None: This fixture yields control back to the test.
        """
        # Store original overrides to restore later
        original_overrides = client.app.dependency_overrides.copy()

        # Override the processor dependencies
        from app.legacy.v2.notifications.services.providers import (
            get_phone_number_sms_processor,
            get_recipient_identifier_sms_processor,
        )

        client.app.dependency_overrides[get_phone_number_sms_processor] = lambda: mock_phone_processor
        client.app.dependency_overrides[get_recipient_identifier_sms_processor] = lambda: mock_recipient_processor

        yield

        # Restore original overrides after test
        client.app.dependency_overrides = original_overrides

    @pytest.mark.parametrize('route', sms_routes)
    @patch('app.legacy.v2.notifications.rest.validate_template')
    async def test_sms_with_phone_number(
        self,
        mock_validate_template: AsyncMock,
        mock_phone_processor: AsyncMock,
        mock_recipient_processor: AsyncMock,
        setup_dependencies: None,
        client: ENPTestClient,
        route: str,
        sms_phone_request: dict,
    ) -> None:
        """Test SMS notification with phone number.

        Args:
            mock_validate_template: Mock for validate_template function
            mock_phone_processor: Mock PhoneNumberSmsProcessor fixture
            mock_recipient_processor: Mock RecipientIdentifierSmsProcessor fixture
            setup_dependencies: Fixture to setup dependency overrides
            client: Test client
            route: Route to test
            sms_phone_request: Request data with phone number
        """
        # Arrange
        mock_validate_template.return_value = None
        mock_phone_processor.process.return_value = None
        mock_recipient_processor.process.return_value = None

        # Act
        response = client.post(route, json=sms_phone_request)

        # Assert
        assert response.status_code == status.HTTP_201_CREATED
        mock_validate_template.assert_called_once_with(self.template_id, NotificationType.SMS, None)
        mock_phone_processor.process.assert_called_once()
        mock_recipient_processor.process.assert_not_called()
        # Verify phone number was passed as a kwarg
        assert 'phone_number' in mock_phone_processor.process.call_args.kwargs
        assert mock_phone_processor.process.call_args.kwargs['phone_number'] == '+18005550101'

    @pytest.mark.parametrize('route', sms_routes)
    @patch('app.legacy.v2.notifications.rest.validate_template')
    async def test_sms_with_recipient_identifier(
        self,
        mock_validate_template: AsyncMock,
        mock_phone_processor: AsyncMock,
        mock_recipient_processor: AsyncMock,
        setup_dependencies: None,
        client: ENPTestClient,
        route: str,
        sms_recipient_id_request: dict,
    ) -> None:
        """Test SMS notification with recipient identifier.

        Args:
            mock_validate_template: Mock for validate_template function
            mock_phone_processor: Mock PhoneNumberSmsProcessor fixture
            mock_recipient_processor: Mock RecipientIdentifierSmsProcessor fixture
            setup_dependencies: Fixture to setup dependency overrides
            client: Test client
            route: Route to test
            sms_recipient_id_request: Request data with recipient identifier
        """
        # Arrange
        mock_validate_template.return_value = None
        mock_phone_processor.process.return_value = None
        mock_recipient_processor.process.return_value = None

        # Act
        response = client.post(route, json=sms_recipient_id_request)

        # Assert
        assert response.status_code == status.HTTP_201_CREATED
        mock_validate_template.assert_called_once_with(self.template_id, NotificationType.SMS, None)
        mock_phone_processor.process.assert_not_called()
        mock_recipient_processor.process.assert_called_once()
        # Verify recipient_identifier was passed as a kwarg
        assert 'recipient_identifier' in mock_recipient_processor.process.call_args.kwargs
        assert mock_recipient_processor.process.call_args.kwargs['recipient_identifier'].id_type == IdentifierType.ICN
        assert mock_recipient_processor.process.call_args.kwargs['recipient_identifier'].id_value == '1234567890V123456'

    @pytest.mark.parametrize('route', sms_routes)
    @patch('app.legacy.v2.notifications.rest.validate_template')
    async def test_sms_with_both_identifiers(
        self,
        mock_validate_template: AsyncMock,
        mock_phone_processor: AsyncMock,
        mock_recipient_processor: AsyncMock,
        setup_dependencies: None,
        client: ENPTestClient,
        route: str,
        sms_both_identifiers_request: dict,
    ) -> None:
        """Test SMS notification with both phone number and recipient identifier.

        Args:
            mock_validate_template: Mock for validate_template function
            mock_phone_processor: Mock PhoneNumberSmsProcessor fixture
            mock_recipient_processor: Mock RecipientIdentifierSmsProcessor fixture
            setup_dependencies: Fixture to setup dependency overrides
            client: Test client
            route: Route to test
            sms_both_identifiers_request: Request data with both identifiers
        """
        # Arrange
        mock_validate_template.return_value = None
        mock_phone_processor.process.return_value = None
        mock_recipient_processor.process.return_value = None

        # Act
        response = client.post(route, json=sms_both_identifiers_request)

        # Assert
        assert response.status_code == status.HTTP_201_CREATED
        mock_validate_template.assert_called_once_with(self.template_id, NotificationType.SMS, None)
        mock_phone_processor.process.assert_called_once()
        mock_recipient_processor.process.assert_not_called()
        # Verify both phone number was passed as kwarg (the router prioritizes phone number if both are present)
        assert 'phone_number' in mock_phone_processor.process.call_args.kwargs

    @pytest.mark.parametrize('route', sms_routes)
    @patch('app.legacy.v2.notifications.rest.validate_template')
    async def test_sms_with_processor_error(
        self,
        mock_validate_template: AsyncMock,
        mock_phone_processor: AsyncMock,
        mock_recipient_processor: AsyncMock,
        setup_dependencies: None,
        client: ENPTestClient,
        route: str,
        sms_phone_request: dict,
    ) -> None:
        """Test SMS notification when processor raises an error.

        Args:
            mock_validate_template: Mock for validate_template function
            mock_phone_processor: Mock PhoneNumberSmsProcessor fixture
            mock_recipient_processor: Mock RecipientIdentifierSmsProcessor fixture
            setup_dependencies: Fixture to setup dependency overrides
            client: Test client
            route: Route to test
            sms_phone_request: Request data
        """
        # Arrange
        mock_validate_template.return_value = None
        mock_phone_processor.process.side_effect = ValueError('Test error')
        mock_recipient_processor.process.return_value = None

        # Act & Assert
        response = client.post(route, json=sms_phone_request)

        # The error should be caught and converted to a 400 Bad Request
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        error_details = response.json()
        assert 'errors' in error_details
        assert len(error_details['errors']) == 1
        assert error_details['errors'][0]['message'] == 'Test error'

        # Verify the mock was actually called before the exception
        mock_phone_processor.process.assert_called_once()
        mock_recipient_processor.process.assert_not_called()

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
