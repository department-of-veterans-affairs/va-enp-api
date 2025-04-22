"""Test module for app/legacy/v2/notifications/services implementations."""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.constants import IdentifierType
from app.legacy.v2.notifications.route_schema import RecipientIdentifierModel
from app.legacy.v2.notifications.services.implementations import (
    DirectPhoneNumberSmsProcessor,
    DirectRecipientIdentifierSmsProcessor,
)


class TestDirectPhoneNumberSmsProcessor:
    """Tests for the DirectPhoneNumberSmsProcessor class."""

    @pytest.fixture
    def processor(self) -> DirectPhoneNumberSmsProcessor:
        """Create a DirectPhoneNumberSmsProcessor instance.

        Returns:
            DirectPhoneNumberSmsProcessor: A processor instance.
        """
        return DirectPhoneNumberSmsProcessor()

    @pytest.mark.asyncio
    async def test_process(self, processor: DirectPhoneNumberSmsProcessor) -> None:
        """Test that process calls _deliver_sms correctly."""
        # Arrange
        notification_id = uuid4()
        phone_number = '+18005551234'
        template_id = uuid4()
        personalisation = {'name': 'Test User'}

        # Mock the _deliver_sms method
        processor._deliver_sms = AsyncMock()

        # Act
        await processor.process(
            notification_id=notification_id,
            template_id=template_id,
            phone_number=phone_number,
            personalisation=personalisation,
        )

        # Assert
        processor._deliver_sms.assert_called_once_with(
            notification_id=notification_id,
            phone_number=phone_number,
            template_id=template_id,
            personalisation=personalisation,
        )

    @pytest.mark.asyncio
    async def test_process_without_personalisation(self, processor: DirectPhoneNumberSmsProcessor) -> None:
        """Test process without personalisation parameter."""
        # Arrange
        notification_id = uuid4()
        phone_number = '+18005551234'
        template_id = uuid4()

        # Mock the _deliver_sms method
        processor._deliver_sms = AsyncMock()

        # Act
        await processor.process(
            notification_id=notification_id,
            template_id=template_id,
            phone_number=phone_number,
        )

        # Assert
        processor._deliver_sms.assert_called_once_with(
            notification_id=notification_id,
            phone_number=phone_number,
            template_id=template_id,
            personalisation=None,
        )

    @pytest.mark.asyncio
    async def test_process_with_extra_kwargs(self, processor: DirectPhoneNumberSmsProcessor) -> None:
        """Test process with extra keyword arguments."""
        # Arrange
        notification_id = uuid4()
        phone_number = '+18005551234'
        template_id = uuid4()

        # Mock the _deliver_sms method
        processor._deliver_sms = AsyncMock()

        # Act
        await processor.process(
            notification_id=notification_id,
            template_id=template_id,
            phone_number=phone_number,
            extra_param='should be ignored',
        )

        # Assert
        processor._deliver_sms.assert_called_once_with(
            notification_id=notification_id,
            phone_number=phone_number,
            template_id=template_id,
            personalisation=None,
        )

    @pytest.mark.asyncio
    async def test_process_raises_error_without_phone_number(self, processor: DirectPhoneNumberSmsProcessor) -> None:
        """Test that process raises a ValueError when phone_number is not provided."""
        # Arrange
        notification_id = uuid4()
        template_id = uuid4()

        # Act & Assert
        with pytest.raises(ValueError, match='phone_number is required for this processor'):
            await processor.process(
                notification_id=notification_id,
                template_id=template_id,
            )

    @pytest.mark.asyncio
    async def test_deliver_sms(self, processor: DirectPhoneNumberSmsProcessor) -> None:
        """Test that _deliver_sms doesn't raise any errors."""
        # Arrange
        notification_id = uuid4()
        phone_number = '+18005551234'
        template_id = uuid4()
        personalisation = {'name': 'Test User'}

        # Act & Assert - Just make sure it doesn't raise an exception
        await processor._deliver_sms(
            notification_id=notification_id,
            phone_number=phone_number,
            template_id=template_id,
            personalisation=personalisation,
        )


class TestDirectRecipientIdentifierSmsProcessor:
    """Tests for the DirectRecipientIdentifierSmsProcessor class."""

    @pytest.fixture
    def processor(self) -> DirectRecipientIdentifierSmsProcessor:
        """Create a DirectRecipientIdentifierSmsProcessor instance.

        Returns:
            DirectRecipientIdentifierSmsProcessor: A processor instance.
        """
        return DirectRecipientIdentifierSmsProcessor()

    @pytest.fixture
    def recipient_identifier(self) -> RecipientIdentifierModel:
        """Create a RecipientIdentifierModel for testing.

        Returns:
            RecipientIdentifierModel: A test recipient identifier.
        """
        return RecipientIdentifierModel(id_type=IdentifierType.ICN, id_value='1234567890V123456')

    @pytest.mark.asyncio
    async def test_process(
        self,
        processor: DirectRecipientIdentifierSmsProcessor,
        recipient_identifier: RecipientIdentifierModel,
    ) -> None:
        """Test that process calls _lookup_recipient_and_send correctly."""
        # Arrange
        notification_id = uuid4()
        template_id = uuid4()
        personalisation = {'name': 'Test User'}

        # Mock the _lookup_recipient_and_send method
        processor._lookup_recipient_and_send = AsyncMock()

        # Act
        await processor.process(
            notification_id=notification_id,
            template_id=template_id,
            recipient_identifier=recipient_identifier,
            personalisation=personalisation,
        )

        # Assert
        processor._lookup_recipient_and_send.assert_called_once_with(
            notification_id=notification_id,
            recipient_identifier=recipient_identifier,
            template_id=template_id,
            personalisation=personalisation,
        )

    @pytest.mark.asyncio
    async def test_process_without_personalisation(
        self,
        processor: DirectRecipientIdentifierSmsProcessor,
        recipient_identifier: RecipientIdentifierModel,
    ) -> None:
        """Test process without personalisation parameter."""
        # Arrange
        notification_id = uuid4()
        template_id = uuid4()

        # Mock the _lookup_recipient_and_send method
        processor._lookup_recipient_and_send = AsyncMock()

        # Act
        await processor.process(
            notification_id=notification_id,
            template_id=template_id,
            recipient_identifier=recipient_identifier,
        )

        # Assert
        processor._lookup_recipient_and_send.assert_called_once_with(
            notification_id=notification_id,
            recipient_identifier=recipient_identifier,
            template_id=template_id,
            personalisation=None,
        )

    @pytest.mark.asyncio
    async def test_process_with_extra_kwargs(
        self,
        processor: DirectRecipientIdentifierSmsProcessor,
        recipient_identifier: RecipientIdentifierModel,
    ) -> None:
        """Test process with extra keyword arguments."""
        # Arrange
        notification_id = uuid4()
        template_id = uuid4()

        # Mock the _lookup_recipient_and_send method
        processor._lookup_recipient_and_send = AsyncMock()

        # Act
        await processor.process(
            notification_id=notification_id,
            template_id=template_id,
            recipient_identifier=recipient_identifier,
            extra_param='should be ignored',
        )

        # Assert
        processor._lookup_recipient_and_send.assert_called_once_with(
            notification_id=notification_id,
            recipient_identifier=recipient_identifier,
            template_id=template_id,
            personalisation=None,
        )

    @pytest.mark.asyncio
    async def test_process_raises_error_without_recipient_identifier(
        self, processor: DirectRecipientIdentifierSmsProcessor
    ) -> None:
        """Test that process raises a ValueError when recipient_identifier is not provided."""
        # Arrange
        notification_id = uuid4()
        template_id = uuid4()

        # Act & Assert
        with pytest.raises(ValueError, match='recipient_identifier is required for this processor'):
            await processor.process(
                notification_id=notification_id,
                template_id=template_id,
            )

    @pytest.mark.asyncio
    async def test_lookup_recipient_and_send(
        self, processor: DirectRecipientIdentifierSmsProcessor, recipient_identifier: RecipientIdentifierModel
    ) -> None:
        """Test that _lookup_recipient_and_send doesn't raise any errors."""
        # Arrange
        notification_id = uuid4()
        template_id = uuid4()
        personalisation = {'name': 'Test User'}

        # Act & Assert - Just make sure it doesn't raise an exception
        await processor._lookup_recipient_and_send(
            notification_id=notification_id,
            recipient_identifier=recipient_identifier,
            template_id=template_id,
            personalisation=personalisation,
        )
