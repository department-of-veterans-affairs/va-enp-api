"""Test module for app/legacy/v2/notifications/services/providers.py."""

from unittest.mock import MagicMock

import pytest
from fastapi import BackgroundTasks

from app.constants import IdentifierType
from app.legacy.v2.notifications.route_schema import RecipientIdentifierModel
from app.legacy.v2.notifications.services.implementations import (
    BackgroundTaskRecipientLookupService,
    BackgroundTaskSmsDeliveryService,
    DefaultPhoneNumberSmsProcessor,
    DefaultRecipientIdentifierSmsProcessor,
)
from app.legacy.v2.notifications.services.providers import (
    get_phone_number_sms_processor,
    get_recipient_identifier_sms_processor,
    get_recipient_lookup_service,
    get_sms_delivery_service,
    get_sms_processor,
)


class TestServiceProviders:
    """Tests for service provider functions."""

    @pytest.fixture
    def background_tasks(self) -> MagicMock:
        """Create a mock BackgroundTasks object.

        Returns:
            MagicMock: A mock BackgroundTasks object.
        """
        return MagicMock(spec=BackgroundTasks)

    def test_get_sms_delivery_service(self, background_tasks: MagicMock) -> None:
        """Test that get_sms_delivery_service returns the expected service type."""
        # Act
        service = get_sms_delivery_service(background_tasks)

        # Assert
        assert isinstance(service, BackgroundTaskSmsDeliveryService)
        assert service.background_tasks == background_tasks

    def test_get_recipient_lookup_service(self, background_tasks: MagicMock) -> None:
        """Test that get_recipient_lookup_service returns the expected service type."""
        # Act
        service = get_recipient_lookup_service(background_tasks)

        # Assert
        assert isinstance(service, BackgroundTaskRecipientLookupService)
        assert service.background_tasks == background_tasks

    def test_get_phone_number_sms_processor(self) -> None:
        """Test that get_phone_number_sms_processor returns the expected processor type."""
        # Arrange
        delivery_service = MagicMock()

        # Act
        processor = get_phone_number_sms_processor(delivery_service)

        # Assert
        assert isinstance(processor, DefaultPhoneNumberSmsProcessor)
        assert processor.delivery_service == delivery_service

    def test_get_recipient_identifier_sms_processor(self) -> None:
        """Test that get_recipient_identifier_sms_processor returns the expected processor type."""
        # Arrange
        lookup_service = MagicMock()

        # Act
        processor = get_recipient_identifier_sms_processor(lookup_service)

        # Assert
        assert isinstance(processor, DefaultRecipientIdentifierSmsProcessor)
        assert processor.lookup_service == lookup_service

    def test_get_sms_processor_with_phone_number(self) -> None:
        """Test that get_sms_processor returns phone processor when phone_number is provided."""
        # Arrange
        phone_number = '+18005551234'
        phone_processor = MagicMock()
        recipient_processor = MagicMock()

        # Act
        processor = get_sms_processor(
            phone_number=phone_number,
            phone_number_processor=phone_processor,
            recipient_identifier_processor=recipient_processor,
        )

        # Assert
        assert processor == phone_processor

    def test_get_sms_processor_with_recipient_identifier(self) -> None:
        """Test that get_sms_processor returns recipient processor when recipient_identifier is provided."""
        # Arrange
        recipient_identifier = RecipientIdentifierModel(id_type=IdentifierType.ICN, id_value='1234567890V123456')
        phone_processor = MagicMock()
        recipient_processor = MagicMock()

        # Act
        processor = get_sms_processor(
            recipient_identifier=recipient_identifier,
            phone_number_processor=phone_processor,
            recipient_identifier_processor=recipient_processor,
        )

        # Assert
        assert processor == recipient_processor

    def test_get_sms_processor_with_both_identifiers(self) -> None:
        """Test that get_sms_processor prioritizes phone_number when both are provided."""
        # Arrange
        phone_number = '+18005551234'
        recipient_identifier = RecipientIdentifierModel(id_type=IdentifierType.ICN, id_value='1234567890V123456')
        phone_processor = MagicMock()
        recipient_processor = MagicMock()

        # Act
        processor = get_sms_processor(
            phone_number=phone_number,
            recipient_identifier=recipient_identifier,
            phone_number_processor=phone_processor,
            recipient_identifier_processor=recipient_processor,
        )

        # Assert
        assert processor == phone_processor

    def test_get_sms_processor_raises_error_without_identifiers(self) -> None:
        """Test that get_sms_processor raises ValueError when neither identifier is provided."""
        # Arrange
        phone_processor = MagicMock()
        recipient_processor = MagicMock()

        # Act and Assert
        with pytest.raises(ValueError, match='Either phone_number or recipient_identifier must be provided'):
            get_sms_processor(
                phone_number_processor=phone_processor,
                recipient_identifier_processor=recipient_processor,
            )
