"""Test module for app/legacy/v2/notifications/utils.py."""

from typing import Any, Awaitable, Callable
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException, status
from fastapi.exceptions import RequestValidationError
from sqlalchemy import Row
from sqlalchemy.exc import NoResultFound

from app.constants import RESPONSE_500, NotificationType
from app.exceptions import NonRetryableError
from app.legacy.clients.sqs import SqsAsyncProducer
from app.legacy.v2.notifications.route_schema import V2PostSmsRequestModel
from app.legacy.v2.notifications.utils import (
    _validate_template_active,
    _validate_template_personalisation,
    _validate_template_type,
    create_notification,
    enqueue_notification_tasks,
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

    async def test_validate_template(self, sample_template: Callable[..., Awaitable[Row[Any]]]) -> None:
        """Test validate_template for happy path."""
        template = await sample_template()

        with patch('app.legacy.v2.notifications.utils.LegacyTemplateDao.get_template', return_value=template):
            # validate_template either runs successfully or raises an exception
            await validate_template(template.id, NotificationType.SMS, None)

    async def test_validate_template_with_personalisation(
        self, sample_template: Callable[..., Awaitable[Row[Any]]]
    ) -> None:
        """Test validate_template for happy path."""
        template = await sample_template(content='before ((content)) after')

        with patch('app.legacy.v2.notifications.utils.LegacyTemplateDao.get_template', return_value=template):
            # validate_template either runs successfully or raises an exception
            await validate_template(template.id, NotificationType.SMS, {'Content': 'test content'})

    async def test_validate_template_raises_exception_when_template_not_found(self) -> None:
        """Test validate_template raises an exception when the template is not found."""
        with patch('app.legacy.v2.notifications.utils.LegacyTemplateDao.get_template', side_effect=NoResultFound):
            with pytest.raises(RequestValidationError) as exc_info:
                await validate_template(uuid4(), NotificationType.SMS, None)
            assert exc_info.value.errors()[0]['msg'] == 'Template not found'

    async def test_validate_template_raises_exception_when_template_not_expected_type(
        self,
        sample_template: Callable[..., Awaitable[Row[Any]]],
    ) -> None:
        """Test validate_template raises an exception when the template is not found."""
        template = await sample_template(template_type=NotificationType.EMAIL)

        with patch('app.legacy.v2.notifications.utils.LegacyTemplateDao.get_template', return_value=template):
            with pytest.raises(RequestValidationError) as exc_info:
                await validate_template(template.id, NotificationType.SMS, None)
            assert exc_info.value.errors()[0]['msg'] == (
                f'{NotificationType.EMAIL} template is not suitable for {NotificationType.SMS} notification'
            )

    async def test_validate_template_type_raises_exception_when_template_not_expected_type(self) -> None:
        """Test validate_template raises an exception when the template is not found."""
        with pytest.raises(
            ValueError,
            match=f'{NotificationType.EMAIL} template is not suitable for {NotificationType.SMS} notification',
        ):
            _validate_template_type(NotificationType.EMAIL, NotificationType.SMS, uuid4())

    async def test_validate_template_raises_exception_when_template_not_active(
        self,
        sample_template: Callable[..., Awaitable[Row[Any]]],
    ) -> None:
        """Test validate_template raises an exception when the template is not found."""
        template = await sample_template(archived=True)

        with patch('app.legacy.v2.notifications.utils.LegacyTemplateDao.get_template', return_value=template):
            with pytest.raises(RequestValidationError) as exc_info:
                await validate_template(template.id, NotificationType.SMS, None)
            assert exc_info.value.errors()[0]['msg'] == 'Template is not active'

    async def test_validate_template_active_raises_exception_when_template_not_active(self) -> None:
        """Test validate_template raises an exception when the template is not found."""
        with pytest.raises(ValueError, match='Template is not active'):
            _validate_template_active(archived=True, template_id=uuid4())

    async def test_validate_template_raises_exception_when_missing_personalisation(
        self,
        sample_template: Callable[..., Awaitable[Row[Any]]],
    ) -> None:
        """Test validate_template raises an exception when personalisation is missing."""
        template = await sample_template(content='before ((content)) after')

        with patch('app.legacy.v2.notifications.utils.LegacyTemplateDao.get_template', return_value=template):
            with pytest.raises(RequestValidationError) as exc_info:
                await validate_template(template.id, NotificationType.SMS, {})
            assert exc_info.value.errors()[0]['msg'] == 'Missing personalisation: content'

    async def test_validate_template_personalisation_raises_exception_when_missing_personalisation(self) -> None:
        """Test validate_template raises an exception when personalisation is missing."""
        with pytest.raises(ValueError, match='Missing personalisation: content'):
            _validate_template_personalisation('before ((content)) after', {'foo': 'bar'}, uuid4())


async def test_enqueue_notification_tasks() -> None:
    """Test enqueue_notification_tasks."""
    q_name = 'queue_name'
    test_data = [(q_name, ('task_name', uuid4()))]

    with patch.object(SqsAsyncProducer, 'enqueue_message') as mock_enqueue:
        await enqueue_notification_tasks(test_data)

    mock_enqueue.assert_called_once()
    assert mock_enqueue.call_args[0][0] == q_name


async def test_create_notification_happy_path(mocker: AsyncMock) -> None:
    """Validate functionality of create_notification.

    Args:
        mocker (AsyncMock): Mock object
    """
    request = V2PostSmsRequestModel(phone_number='+18005550101', template_id=uuid4())
    mocker.patch('app.legacy.v2.notifications.utils.LegacyNotificationDao.create_notification')
    mock_context = mocker.patch('app.legacy.v2.notifications.utils.context')
    mock_context.api_key = uuid4()
    mock_context.service_id = uuid4()
    await create_notification(uuid4(), mocker.AsyncMock(), request)


async def test_create_notification_failure(mocker: AsyncMock) -> None:
    """Fail to create notification due to a NonRetryableError.

    Args:
        mocker (AsyncMock): Mock object
    """
    request = V2PostSmsRequestModel(phone_number='+18005550101', template_id=uuid4())
    mocker.patch(
        'app.legacy.v2.notifications.utils.LegacyNotificationDao.create_notification', side_effect=NonRetryableError
    )
    mock_context = mocker.patch('app.legacy.v2.notifications.utils.context')
    mock_context.api_key = uuid4()
    mock_context.service_id = uuid4()

    with pytest.raises(HTTPException) as exc_info:
        await create_notification(uuid4(), mocker.AsyncMock(), request)
    assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert exc_info.value.detail == RESPONSE_500
