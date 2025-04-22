"""Test module for app/legacy/v2/notifications/services/providers.py."""

from unittest.mock import MagicMock

import pytest
from fastapi import BackgroundTasks

from app.legacy.v2.notifications.services.implementations import (
    BackgroundTaskRecipientLookupService,
    BackgroundTaskSmsDeliveryService,
    DefaultSmsProcessor,
)
from app.legacy.v2.notifications.services.providers import (
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

    def test_get_sms_processor(self) -> None:
        """Test that get_sms_processor returns the expected processor type."""
        # Arrange
        delivery_service = MagicMock()
        lookup_service = MagicMock()

        # Act
        processor = get_sms_processor(delivery_service, lookup_service)

        # Assert
        assert isinstance(processor, DefaultSmsProcessor)
        assert processor.delivery_service == delivery_service
        assert processor.lookup_service == lookup_service
