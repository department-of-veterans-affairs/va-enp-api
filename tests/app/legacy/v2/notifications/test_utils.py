"""Test module for app/legacy/v2/notifications/utils.py."""

from typing import Any, Awaitable, Callable
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import Row
from sqlalchemy.exc import NoResultFound

from app.constants import NotificationType
from app.exceptions import NonRetryableError
from app.legacy.v2.notifications.utils import (
    _validate_template_active,
    _validate_template_type,
    get_arn_from_icn,
    send_push_notification_helper,
    validate_push_template,
    validate_template,
    validate_template_personalisation,
)
from app.providers.provider_aws import ProviderAWS

# TODO 134 Add specific tests for  _validate_template_service


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

    @pytest.mark.parametrize(
        'msg_template', ['stub message ((name))', 'stub message'], ids=('personalization', 'no_personalization')
    )
    @patch('app.legacy.v2.notifications.utils.get_arn_from_icn', return_value='test_arn')
    async def test_send_push_notification_helper(
        self, mock_get_arn_from_icn: dict[str, str | int] | None, msg_template: str
    ) -> None:
        """Test send_push_notification_helper.

        Most of the code called in this function is not implemented yet. It is being mocked out for now.
        We are just checking the proper calls are made.
        """
        mock_provider = AsyncMock(spec=ProviderAWS)
        personalisation: dict[str, str | int | float] = {'name': 'John'}

        await send_push_notification_helper(personalisation, '12345', msg_template, mock_provider)

        mock_provider.send_notification.assert_called_once()

    @patch('app.legacy.v2.notifications.utils.logger.exception')
    @patch('app.legacy.v2.notifications.utils.get_arn_from_icn', return_value='test_arn')
    async def test_send_push_notification_helper_logs_exception(
        self, mock_get_arn_from_icn: AsyncMock | None, mock_logger: AsyncMock
    ) -> None:
        """Test send_push_notification_helper."""
        mock_provider = AsyncMock(spec=ProviderAWS)
        mock_provider.send_notification.side_effect = NonRetryableError
        personalisation: dict[str, str | int | float] = {'name': 'John'}

        await send_push_notification_helper(personalisation, '12345', 'mock message template', mock_provider)

        mock_logger.assert_called_once()

    async def test_send_push_notification_helper_throws_not_implemented(self) -> None:
        """Test send_push_notification_helper, which currently throws a not implemented error."""
        mock_provider = AsyncMock(spec=ProviderAWS)

        with pytest.raises(NotImplementedError):
            await send_push_notification_helper(None, '12345', 'mock message template', mock_provider)


class TestValidateTemplate:
    """Test validate_template and the functions it calls for each piece of template validation."""

    async def test_validate_template(
        self, sample_template: Callable[..., Awaitable[Row[Any]]], sample_service: Callable[..., Awaitable[Row[Any]]]
    ) -> None:
        """Test validate_template for happy path."""
        service = await sample_service()
        service_id = service.id
        template = await sample_template(service_id=service_id)

        with patch('app.legacy.v2.notifications.utils.LegacyTemplateDao.get_template', return_value=template):
            # validate_template either runs successfully or raises an exception
            await validate_template(template.id, NotificationType.SMS, service_id)

    async def test_validate_template_raises_exception_when_template_not_found(self) -> None:
        """Test validate_template raises an exception when the template is not found."""
        service_id = uuid4()

        with patch('app.legacy.v2.notifications.utils.LegacyTemplateDao.get_template', side_effect=NoResultFound):
            with pytest.raises(NonRetryableError) as error:
                await validate_template(uuid4(), NotificationType.SMS, service_id)

            assert 'Template not found' in str(error.value.log_msg)

    async def test_validate_template_raises_exception_when_template_not_expected_type(
        self,
        sample_template: Callable[..., Awaitable[Row[Any]]],
    ) -> None:
        """Test validate_template raises an exception when the template is wrong type."""
        template = await sample_template(template_type=NotificationType.EMAIL)
        service_id = uuid4()

        with patch('app.legacy.v2.notifications.utils.LegacyTemplateDao.get_template', return_value=template):
            with pytest.raises(NonRetryableError) as error:
                await validate_template(template.id, NotificationType.SMS, service_id)

            assert f'{NotificationType.EMAIL} template is not suitable for {NotificationType.SMS} notification' in str(
                error.value.log_msg
            )

    async def test_validate_template_raises_exception_when_template_not_active(
        self,
        sample_template: Callable[..., Awaitable[Row[Any]]],
    ) -> None:
        """Test validate_template raises an exception when the template is archived."""
        template = await sample_template(archived=True)
        service_id = uuid4()

        with patch('app.legacy.v2.notifications.utils.LegacyTemplateDao.get_template', return_value=template):
            with pytest.raises(NonRetryableError) as error:
                await validate_template(template.id, NotificationType.SMS, service_id)

            assert 'Template is not active' in str(error.value.log_msg)

    async def test_validate_template_raises_exception_when_service_mismatch(
        self,
        sample_template: Callable[..., Awaitable[Row[Any]]],
    ) -> None:
        """Test validate_template raises an exception when the template belongs to wrong service."""
        template = await sample_template()
        different_service_id = uuid4()

        with patch('app.legacy.v2.notifications.utils.LegacyTemplateDao.get_template', return_value=template):
            with pytest.raises(NonRetryableError) as error:
                await validate_template(template.id, NotificationType.SMS, different_service_id)

            assert 'Template does not belong to the specified service' in str(error.value.log_msg)

    async def test_validate_template_type_raises_exception_when_template_not_expected_type(self) -> None:
        """Test _validate_template_type raises an exception when the template is wrong type."""
        with pytest.raises(NonRetryableError) as error:
            _validate_template_type(NotificationType.EMAIL, NotificationType.SMS, uuid4())

        assert f'{NotificationType.EMAIL} template is not suitable for {NotificationType.SMS} notification' in str(
            error.value.log_msg
        )

    async def test_validate_template_active_raises_exception_when_template_not_active(self) -> None:
        """Test _validate_template_active raises an exception when the template is archived."""
        with pytest.raises(NonRetryableError) as error:
            _validate_template_active(archived=True, template_id=uuid4())

        assert 'Template is not active' in str(error.value.log_msg)


class TestValidateTemplatePersonalisation:
    """Test validate_template_personalisation function."""

    async def test_validate_template_personalisation_success(self) -> None:
        """Test validate_template_personalisation for happy path."""
        template_id = uuid4()

        # Should run successfully without raising an exception
        validate_template_personalisation('before ((content)) after', {'content': 'test content'}, template_id)

    async def test_validate_template_personalisation_case_insensitive(self) -> None:
        """Test validate_template_personalisation handles case insensitive matching."""
        template_id = uuid4()

        # Should run successfully with different case
        validate_template_personalisation('before ((Content)) after', {'content': 'test content'}, template_id)

    async def test_validate_template_personalisation_no_personalisation_required(self) -> None:
        """Test validate_template_personalisation when no personalisation is required."""
        template_id = uuid4()

        # Should run successfully with no personalisation
        validate_template_personalisation('simple message with no placeholders', None, template_id)

    async def test_validate_template_personalisation_raises_exception_when_missing_personalisation(self) -> None:
        """Test validate_template_personalisation raises an exception when personalisation is missing."""
        template_id = uuid4()

        with pytest.raises(NonRetryableError) as error:
            validate_template_personalisation('before ((content)) after', {}, template_id)

        assert 'Missing personalisation: content' in str(error.value.log_msg)

    async def test_validate_template_personalisation_raises_exception_when_partially_missing(self) -> None:
        """Test validate_template_personalisation raises an exception when some personalisation is missing."""
        template_id = uuid4()

        with pytest.raises(NonRetryableError) as error:
            validate_template_personalisation('Hello ((name)), your ((item)) is ready', {'name': 'John'}, template_id)

        assert 'Missing personalisation: item' in str(error.value.log_msg)
