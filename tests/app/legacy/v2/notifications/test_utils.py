"""Test module for app/legacy/v2/notifications/utils.py."""

from typing import Callable
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from pydantic import UUID4
from sqlalchemy.exc import NoResultFound

from app.constants import NotificationType
from app.db.models import Template
from app.exceptions import NonRetryableError
from app.legacy.v2.notifications.utils import (
    _validate_template_active,
    _validate_template_personalisation,
    _validate_template_type,
    get_arn_from_icn,
    send_push_notification_helper,
    validate_push_template,
    validate_template,
)
from app.providers.provider_aws import ProviderAWS


async def test_get_arn_from_icn_not_implemented() -> None:
    """Test get_arn_from_icn."""
    with pytest.raises(NotImplementedError):
        await get_arn_from_icn('12345')


async def test_validate_push_template() -> None:
    """Test validate_push_template."""
    with pytest.raises(NotImplementedError):
        await validate_push_template(uuid4())


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
        personalisation: dict[str, str | int | float] = {'name': 'John'}

        await send_push_notification_helper(personalisation, '12345', mock_template, mock_provider)

        mock_provider.send_notification.assert_called_once()

    @patch('app.legacy.v2.notifications.utils.logger.exception')
    @patch('app.legacy.v2.notifications.utils.get_arn_from_icn', return_value='test_arn')
    async def test_send_push_notification_helper_logs_exception(
        self, mock_get_arn_from_icn: AsyncMock | None, mock_logger: AsyncMock
    ) -> None:
        """Test send_push_notification_helper."""
        mock_template = AsyncMock(spec=Template)
        mock_template.build_message.return_value = 'test_message'
        mock_provider = AsyncMock(spec=ProviderAWS)
        mock_provider.send_notification.side_effect = NonRetryableError
        personalization: dict[str, str | int | float] = {'name': 'John'}

        await send_push_notification_helper(personalization, '12345', mock_template, mock_provider)

        mock_logger.assert_called_once()

    async def test_send_push_notification_helper_throws_not_implemented(self) -> None:
        """Test send_push_notification_helper, which currently throws a not implemented error."""
        mock_provider = AsyncMock(spec=ProviderAWS)
        template = Template(name='test_template')

        with pytest.raises(NotImplementedError):
            await send_push_notification_helper(None, '12345', template, mock_provider)


class TestValidateTemplate:
    """Test validate_template and the functions it calls for each piece of template validation."""

    async def test_validate_template(self, mock_template: Callable[..., AsyncMock]) -> None:
        """Test validate_template for happy path."""
        mock_template = mock_template()

        with patch('app.legacy.v2.notifications.utils.LegacyTemplateDao.get_template', return_value=mock_template):
            # validate_template either runs successfully or raises an exception
            await validate_template(mock_template.id, NotificationType.SMS, None)

    async def test_validate_template_with_personalisation(self, mock_template: Callable[..., AsyncMock]) -> None:
        """Test validate_template for happy path."""
        mock_template = mock_template(content='before ((content)) after')

        with patch('app.legacy.v2.notifications.utils.LegacyTemplateDao.get_template', return_value=mock_template):
            # validate_template either runs successfully or raises an exception
            await validate_template(mock_template.id, NotificationType.SMS, {'Content': 'test content'})

    async def test_validate_template_raises_exception_when_template_not_found(self) -> None:
        """Test validate_template raises an exception when the template is not found."""
        with patch('app.legacy.v2.notifications.utils.LegacyTemplateDao.get_template', side_effect=NoResultFound):
            with pytest.raises(ValueError, match='Template not found'):
                await validate_template(UUID4('55dd7dff-76f2-425b-86c2-f5022426a31d'), NotificationType.SMS, None)

    async def test_validate_template_raises_exception_when_template_not_expected_type(
        self,
        mock_template: Callable[..., AsyncMock],
    ) -> None:
        """Test validate_template raises an exception when the template is not found."""
        mock_template = mock_template(template_type=NotificationType.EMAIL)

        with patch('app.legacy.v2.notifications.utils.LegacyTemplateDao.get_template', return_value=mock_template):
            with pytest.raises(
                ValueError,
                match=f'{NotificationType.EMAIL} template is not suitable for {NotificationType.SMS} notification',
            ):
                await validate_template(mock_template.id, NotificationType.SMS, None)

    async def test_validate_template_type_raises_exception_when_template_not_expected_type(self) -> None:
        """Test validate_template raises an exception when the template is not found."""
        with pytest.raises(
            ValueError,
            match=f'{NotificationType.EMAIL} template is not suitable for {NotificationType.SMS} notification',
        ):
            _validate_template_type(NotificationType.EMAIL, NotificationType.SMS, uuid4())

    async def test_validate_template_raises_exception_when_template_not_active(
        self,
        mock_template: Callable[..., AsyncMock],
    ) -> None:
        """Test validate_template raises an exception when the template is not found."""
        mock_template = mock_template(archived=True)

        with patch('app.legacy.v2.notifications.utils.LegacyTemplateDao.get_template', return_value=mock_template):
            with pytest.raises(ValueError, match='Template is not active'):
                await validate_template(mock_template.id, NotificationType.SMS, None)

    async def test_validate_template_active_raises_exception_when_template_not_active(self) -> None:
        """Test validate_template raises an exception when the template is not found."""
        with pytest.raises(ValueError, match='Template is not active'):
            _validate_template_active(archived=True, template_id=uuid4())

    async def test_validate_template_raises_exception_when_missing_personalisation(
        self,
        mock_template: Callable[..., AsyncMock],
    ) -> None:
        """Test validate_template raises an exception when personalisation is missing."""
        mock_template = mock_template(content='before ((content)) after')

        with patch('app.legacy.v2.notifications.utils.LegacyTemplateDao.get_template', return_value=mock_template):
            with pytest.raises(ValueError, match='Missing personalisation: content'):
                await validate_template(mock_template.id, NotificationType.SMS, {})

    async def test_validate_template_personalisation_raises_exception_when_missing_personalisation(self) -> None:
        """Test validate_template raises an exception when personalisation is missing."""
        with pytest.raises(ValueError, match='Missing personalisation: content'):
            _validate_template_personalisation('before ((content)) after', {'foo': 'bar'}, uuid4())
