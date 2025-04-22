"""Test module for app/legacy/v2/notifications/services implementations."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from _pytest.monkeypatch import MonkeyPatch  # Import MonkeyPatch from _pytest
from fastapi import BackgroundTasks

from app.constants import IdentifierType
from app.legacy.v2.notifications.route_schema import RecipientIdentifierModel
from app.legacy.v2.notifications.services.implementations import (
    BackgroundTaskRecipientLookupService,
    BackgroundTaskSmsDeliveryService,
    DefaultPhoneNumberSmsProcessor,
    DefaultRecipientIdentifierSmsProcessor,
)
from app.legacy.v2.notifications.services.interfaces import (
    RecipientLookupService,
    SmsDeliveryService,
)


class TestBackgroundTaskSmsDeliveryService:
    """Tests for the BackgroundTaskSmsDeliveryService class."""

    @pytest.fixture
    def background_tasks(self) -> MagicMock:
        """Create a mock BackgroundTasks object.

        Returns:
            MagicMock: A mock BackgroundTasks object.
        """
        return MagicMock(spec=BackgroundTasks)

    @pytest.fixture
    def service(self, background_tasks: MagicMock) -> BackgroundTaskSmsDeliveryService:
        """Create a BackgroundTaskSmsDeliveryService instance.

        Args:
            background_tasks: A mock BackgroundTasks object.

        Returns:
            BackgroundTaskSmsDeliveryService: A service instance.
        """
        return BackgroundTaskSmsDeliveryService(background_tasks)

    @pytest.mark.asyncio
    async def test_queue_sms_for_delivery(
        self, service: BackgroundTaskSmsDeliveryService, background_tasks: MagicMock
    ) -> None:
        """Test that queue_sms_for_delivery calls add_task with the correct arguments."""
        # Arrange
        notification_id = uuid4()
        phone_number = '+18005551234'
        template_id = uuid4()
        personalisation = {'name': 'Test User'}

        # Act
        await service.queue_sms_for_delivery(
            notification_id=notification_id,
            phone_number=phone_number,
            template_id=template_id,
            personalisation=personalisation,
        )

        # Assert
        background_tasks.add_task.assert_called_once()
        args, kwargs = background_tasks.add_task.call_args
        assert args[0] == service._deliver_sms
        assert kwargs['notification_id'] == notification_id
        assert kwargs['phone_number'] == phone_number
        assert kwargs['template_id'] == template_id
        assert kwargs['personalisation'] == personalisation

    @pytest.mark.asyncio
    async def test_queue_sms_for_delivery_without_personalisation(
        self, service: BackgroundTaskSmsDeliveryService, background_tasks: MagicMock
    ) -> None:
        """Test queue_sms_for_delivery without personalisation parameter."""
        # Arrange
        notification_id = uuid4()
        phone_number = '+18005551234'
        template_id = uuid4()

        # Act
        await service.queue_sms_for_delivery(
            notification_id=notification_id,
            phone_number=phone_number,
            template_id=template_id,
        )

        # Assert
        background_tasks.add_task.assert_called_once()
        args, kwargs = background_tasks.add_task.call_args
        assert args[0] == service._deliver_sms
        assert kwargs['notification_id'] == notification_id
        assert kwargs['phone_number'] == phone_number
        assert kwargs['template_id'] == template_id
        assert kwargs['personalisation'] is None

    @pytest.mark.asyncio
    async def test_queue_for_delivery(
        self, service: BackgroundTaskSmsDeliveryService, monkeypatch: MonkeyPatch
    ) -> None:
        """Test that queue_for_delivery delegates to queue_sms_for_delivery."""
        # Arrange
        notification_id = uuid4()
        phone_number = '+18005551234'
        template_id = uuid4()
        personalisation = {'name': 'Test User'}

        # Create a mock for the queue_sms_for_delivery method
        mock_queue = AsyncMock()
        monkeypatch.setattr(service, 'queue_sms_for_delivery', mock_queue)

        # Act
        await service.queue_for_delivery(
            notification_id=notification_id,
            template_id=template_id,
            personalisation=personalisation,
            phone_number=phone_number,
        )

        # Assert
        mock_queue.assert_called_once_with(
            notification_id=notification_id,
            phone_number=phone_number,
            template_id=template_id,
            personalisation=personalisation,
        )

    @pytest.mark.asyncio
    async def test_queue_for_delivery_with_extra_kwargs(
        self, service: BackgroundTaskSmsDeliveryService, monkeypatch: MonkeyPatch
    ) -> None:
        """Test queue_for_delivery with extra keyword arguments."""
        # Arrange
        notification_id = uuid4()
        phone_number = '+18005551234'
        template_id = uuid4()
        personalisation = {'name': 'Test User'}

        # Create a mock for the queue_sms_for_delivery method
        mock_queue = AsyncMock()
        monkeypatch.setattr(service, 'queue_sms_for_delivery', mock_queue)

        # Act
        await service.queue_for_delivery(
            notification_id=notification_id,
            template_id=template_id,
            personalisation=personalisation,
            phone_number=phone_number,
            extra_kwarg='should be ignored',
        )

        # Assert
        mock_queue.assert_called_once_with(
            notification_id=notification_id,
            phone_number=phone_number,
            template_id=template_id,
            personalisation=personalisation,
        )

    @pytest.mark.asyncio
    async def test_queue_for_delivery_raises_error_without_phone_number(
        self, service: BackgroundTaskSmsDeliveryService
    ) -> None:
        """Test that queue_for_delivery raises a ValueError when phone_number is not provided."""
        # Arrange
        notification_id = uuid4()
        template_id = uuid4()

        # Act & Assert
        with pytest.raises(ValueError, match='phone_number is required for SMS delivery'):
            await service.queue_for_delivery(
                notification_id=notification_id,
                template_id=template_id,
            )

    @pytest.mark.asyncio
    async def test_deliver_sms(self, service: BackgroundTaskSmsDeliveryService) -> None:
        """Test that _deliver_sms doesn't raise any errors."""
        # Arrange
        notification_id = uuid4()
        phone_number = '+18005551234'
        template_id = uuid4()
        personalisation = {'name': 'Test User'}

        # Act & Assert - Just make sure it doesn't raise an exception
        await service._deliver_sms(
            notification_id=notification_id,
            phone_number=phone_number,
            template_id=template_id,
            personalisation=personalisation,
        )

    @pytest.mark.asyncio
    async def test_deliver_sms_without_personalisation(self, service: BackgroundTaskSmsDeliveryService) -> None:
        """Test _deliver_sms without personalisation parameter."""
        # Arrange
        notification_id = uuid4()
        phone_number = '+18005551234'
        template_id = uuid4()

        # Act & Assert - Just make sure it doesn't raise an exception
        await service._deliver_sms(
            notification_id=notification_id,
            phone_number=phone_number,
            template_id=template_id,
        )


class TestBackgroundTaskRecipientLookupService:
    """Tests for the BackgroundTaskRecipientLookupService class."""

    @pytest.fixture
    def background_tasks(self) -> MagicMock:
        """Create a mock BackgroundTasks object.

        Returns:
            MagicMock: A mock BackgroundTasks object.
        """
        return MagicMock(spec=BackgroundTasks)

    @pytest.fixture
    def service(self, background_tasks: MagicMock) -> BackgroundTaskRecipientLookupService:
        """Create a BackgroundTaskRecipientLookupService instance.

        Args:
            background_tasks: A mock BackgroundTasks object.

        Returns:
            BackgroundTaskRecipientLookupService: A service instance.
        """
        return BackgroundTaskRecipientLookupService(background_tasks)

    @pytest.fixture
    def recipient_identifier(self) -> RecipientIdentifierModel:
        """Create a RecipientIdentifierModel for testing.

        Returns:
            RecipientIdentifierModel: A test recipient identifier.
        """
        return RecipientIdentifierModel(id_type=IdentifierType.ICN, id_value='1234567890V123456')

    @pytest.mark.asyncio
    async def test_queue_recipient_lookup(
        self,
        service: BackgroundTaskRecipientLookupService,
        background_tasks: MagicMock,
        recipient_identifier: RecipientIdentifierModel,
    ) -> None:
        """Test that queue_recipient_lookup calls add_task with the correct arguments."""
        # Arrange
        notification_id = uuid4()
        template_id = uuid4()
        personalisation = {'name': 'Test User'}

        # Act
        await service.queue_recipient_lookup(
            notification_id=notification_id,
            recipient_identifier=recipient_identifier,
            template_id=template_id,
            personalisation=personalisation,
        )

        # Assert
        background_tasks.add_task.assert_called_once()
        args, kwargs = background_tasks.add_task.call_args
        assert args[0] == service._lookup_recipient_info
        assert kwargs['notification_id'] == notification_id
        assert kwargs['recipient_identifier'] == recipient_identifier
        assert kwargs['template_id'] == template_id
        assert kwargs['personalisation'] == personalisation

    @pytest.mark.asyncio
    async def test_queue_recipient_lookup_without_personalisation(
        self,
        service: BackgroundTaskRecipientLookupService,
        background_tasks: MagicMock,
        recipient_identifier: RecipientIdentifierModel,
    ) -> None:
        """Test queue_recipient_lookup without personalisation parameter."""
        # Arrange
        notification_id = uuid4()
        template_id = uuid4()

        # Act
        await service.queue_recipient_lookup(
            notification_id=notification_id,
            recipient_identifier=recipient_identifier,
            template_id=template_id,
        )

        # Assert
        background_tasks.add_task.assert_called_once()
        args, kwargs = background_tasks.add_task.call_args
        assert args[0] == service._lookup_recipient_info
        assert kwargs['notification_id'] == notification_id
        assert kwargs['recipient_identifier'] == recipient_identifier
        assert kwargs['template_id'] == template_id
        assert kwargs['personalisation'] is None

    @pytest.mark.asyncio
    async def test_lookup_recipient_info(
        self, service: BackgroundTaskRecipientLookupService, recipient_identifier: RecipientIdentifierModel
    ) -> None:
        """Test that _lookup_recipient_info doesn't raise any errors."""
        # Arrange
        notification_id = uuid4()
        template_id = uuid4()
        personalisation = {'name': 'Test User'}

        # Act & Assert - Just make sure it doesn't raise an exception
        await service._lookup_recipient_info(
            notification_id=notification_id,
            recipient_identifier=recipient_identifier,
            template_id=template_id,
            personalisation=personalisation,
        )

    @pytest.mark.asyncio
    async def test_lookup_recipient_info_without_personalisation(
        self, service: BackgroundTaskRecipientLookupService, recipient_identifier: RecipientIdentifierModel
    ) -> None:
        """Test _lookup_recipient_info without personalisation parameter."""
        # Arrange
        notification_id = uuid4()
        template_id = uuid4()

        # Act & Assert - Just make sure it doesn't raise an exception
        await service._lookup_recipient_info(
            notification_id=notification_id,
            recipient_identifier=recipient_identifier,
            template_id=template_id,
        )


class TestDefaultPhoneNumberSmsProcessor:
    """Tests for the DefaultPhoneNumberSmsProcessor class."""

    @pytest.fixture
    def delivery_service(self) -> MagicMock:
        """Create a mock SmsDeliveryService.

        Returns:
            MagicMock: A mock delivery service.
        """
        mock = MagicMock(spec=SmsDeliveryService)
        mock.queue_sms_for_delivery = AsyncMock()
        return mock

    @pytest.fixture
    def processor(self, delivery_service: MagicMock) -> DefaultPhoneNumberSmsProcessor:
        """Create a DefaultPhoneNumberSmsProcessor instance.

        Args:
            delivery_service: A mock delivery service.

        Returns:
            DefaultPhoneNumberSmsProcessor: A processor instance.
        """
        return DefaultPhoneNumberSmsProcessor(delivery_service=delivery_service)

    @pytest.mark.asyncio
    async def test_process(self, processor: DefaultPhoneNumberSmsProcessor, delivery_service: MagicMock) -> None:
        """Test that process calls the delivery service correctly."""
        # Arrange
        notification_id = uuid4()
        phone_number = '+18005551234'
        template_id = uuid4()
        personalisation = {'name': 'Test User'}

        # Act
        await processor.process(
            notification_id=notification_id,
            template_id=template_id,
            phone_number=phone_number,
            personalisation=personalisation,
        )

        # Assert
        delivery_service.queue_sms_for_delivery.assert_called_once_with(
            notification_id=notification_id,
            phone_number=phone_number,
            template_id=template_id,
            personalisation=personalisation,
        )

    @pytest.mark.asyncio
    async def test_process_without_personalisation(
        self, processor: DefaultPhoneNumberSmsProcessor, delivery_service: MagicMock
    ) -> None:
        """Test process without personalisation parameter."""
        # Arrange
        notification_id = uuid4()
        phone_number = '+18005551234'
        template_id = uuid4()

        # Act
        await processor.process(
            notification_id=notification_id,
            template_id=template_id,
            phone_number=phone_number,
        )

        # Assert
        delivery_service.queue_sms_for_delivery.assert_called_once_with(
            notification_id=notification_id,
            phone_number=phone_number,
            template_id=template_id,
            personalisation=None,
        )

    @pytest.mark.asyncio
    async def test_process_with_extra_kwargs(
        self, processor: DefaultPhoneNumberSmsProcessor, delivery_service: MagicMock
    ) -> None:
        """Test process with extra keyword arguments."""
        # Arrange
        notification_id = uuid4()
        phone_number = '+18005551234'
        template_id = uuid4()

        # Act
        await processor.process(
            notification_id=notification_id,
            template_id=template_id,
            phone_number=phone_number,
            extra_param='should be ignored',
        )

        # Assert
        delivery_service.queue_sms_for_delivery.assert_called_once_with(
            notification_id=notification_id,
            phone_number=phone_number,
            template_id=template_id,
            personalisation=None,
        )


class TestDefaultRecipientIdentifierSmsProcessor:
    """Tests for the DefaultRecipientIdentifierSmsProcessor class."""

    @pytest.fixture
    def lookup_service(self) -> MagicMock:
        """Create a mock RecipientLookupService.

        Returns:
            MagicMock: A mock lookup service.
        """
        mock = MagicMock(spec=RecipientLookupService)
        mock.queue_recipient_lookup = AsyncMock()
        return mock

    @pytest.fixture
    def processor(self, lookup_service: MagicMock) -> DefaultRecipientIdentifierSmsProcessor:
        """Create a DefaultRecipientIdentifierSmsProcessor instance.

        Args:
            lookup_service: A mock lookup service.

        Returns:
            DefaultRecipientIdentifierSmsProcessor: A processor instance.
        """
        return DefaultRecipientIdentifierSmsProcessor(lookup_service=lookup_service)

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
        processor: DefaultRecipientIdentifierSmsProcessor,
        lookup_service: MagicMock,
        recipient_identifier: RecipientIdentifierModel,
    ) -> None:
        """Test that process calls the lookup service correctly."""
        # Arrange
        notification_id = uuid4()
        template_id = uuid4()
        personalisation = {'name': 'Test User'}

        # Act
        await processor.process(
            notification_id=notification_id,
            template_id=template_id,
            recipient_identifier=recipient_identifier,
            personalisation=personalisation,
        )

        # Assert
        lookup_service.queue_recipient_lookup.assert_called_once_with(
            notification_id=notification_id,
            recipient_identifier=recipient_identifier,
            template_id=template_id,
            personalisation=personalisation,
        )

    @pytest.mark.asyncio
    async def test_process_without_personalisation(
        self,
        processor: DefaultRecipientIdentifierSmsProcessor,
        lookup_service: MagicMock,
        recipient_identifier: RecipientIdentifierModel,
    ) -> None:
        """Test process without personalisation parameter."""
        # Arrange
        notification_id = uuid4()
        template_id = uuid4()

        # Act
        await processor.process(
            notification_id=notification_id,
            template_id=template_id,
            recipient_identifier=recipient_identifier,
        )

        # Assert
        lookup_service.queue_recipient_lookup.assert_called_once_with(
            notification_id=notification_id,
            recipient_identifier=recipient_identifier,
            template_id=template_id,
            personalisation=None,
        )

    @pytest.mark.asyncio
    async def test_process_with_extra_kwargs(
        self,
        processor: DefaultRecipientIdentifierSmsProcessor,
        lookup_service: MagicMock,
        recipient_identifier: RecipientIdentifierModel,
    ) -> None:
        """Test process with extra keyword arguments."""
        # Arrange
        notification_id = uuid4()
        template_id = uuid4()

        # Act
        await processor.process(
            notification_id=notification_id,
            template_id=template_id,
            recipient_identifier=recipient_identifier,
            extra_param='should be ignored',
        )

        # Assert
        lookup_service.queue_recipient_lookup.assert_called_once_with(
            notification_id=notification_id,
            recipient_identifier=recipient_identifier,
            template_id=template_id,
            personalisation=None,
        )
