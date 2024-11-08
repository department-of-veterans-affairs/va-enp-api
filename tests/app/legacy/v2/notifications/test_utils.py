"""Test module for app/legacy/v2/notifications/utils.py."""

from unittest.mock import AsyncMock, patch

import pytest

from app.db.models import Template
from app.legacy.v2.notifications.utils import get_arn_from_icn, send_push_notification_helper, validate_template
from app.providers.provider_aws import ProviderAWS
from app.providers.provider_base import ProviderNonRetryableError


@pytest.mark.asyncio
async def test_get_arn_from_icn_not_implemented() -> None:
    """Test get_arn_from_icn."""
    with pytest.raises(NotImplementedError):
        await get_arn_from_icn('12345')


@pytest.mark.asyncio
async def test_validate_template_not_implemented() -> None:
    """Test validate_template."""
    with pytest.raises(NotImplementedError):
        await validate_template('d5b6e67c-8e2a-11ee-8b8e-0242ac120002')


@pytest.mark.asyncio
class TestSendPushNotificationHelper:
    """Test send_push_notification_helper."""

    @patch('app.legacy.v2.notifications.utils.get_arn_from_icn', return_value='test_arn')
    async def test_send_push_notification_helper(self, mock_get_arn_from_icn: dict[str, str | int] | None) -> None:
        """Test send_push_notification_helper.

        Most of the code called in this function is not implemented yet. It is being mocked out for now.
        We are just checking the proper calls are made.
        """
        mock_template = AsyncMock(spec=Template)
        mock_template.build_message.return_value = 'test_message'
        mock_provider = AsyncMock(spec=ProviderAWS)
        personalization = {'name': 'John'}

        await send_push_notification_helper(personalization, '12345', mock_template, mock_provider)

        mock_provider.send_notification.assert_called_once()

    @patch('app.legacy.v2.notifications.utils.logger.critical')
    @patch('app.legacy.v2.notifications.utils.get_arn_from_icn', return_value='test_arn')
    async def test_send_push_notification_helper_logs_exception(
        self, mock_get_arn_from_icn: AsyncMock | None, mock_logger: AsyncMock
    ) -> None:
        """Test send_push_notification_helper."""
        mock_template = AsyncMock(spec=Template)
        mock_template.build_message.return_value = 'test_message'
        mock_provider = AsyncMock(spec=ProviderAWS)
        mock_provider.send_notification.side_effect = ProviderNonRetryableError
        personalization = {'name': 'John'}

        await send_push_notification_helper(personalization, '12345', mock_template, mock_provider)

        mock_logger.assert_called_once()

    async def test_send_push_notification_helper_throws_not_implemented(self) -> None:
        """Test send_push_notification_helper."""
        template = Template(name='test_template')
        with pytest.raises(NotImplementedError):
            await send_push_notification_helper(None, '12345', template, None)
