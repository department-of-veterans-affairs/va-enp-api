"""Test module for app/legacy/v2/notifications/utils.py."""

from typing import Any, Awaitable, Callable, cast
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException, status
from sqlalchemy import Row

from app.constants import RESPONSE_500, NotificationType
from app.exceptions import NonRetryableError
from app.legacy.clients.sqs import SqsAsyncProducer
from app.legacy.v2.notifications.route_schema import PersonalisationFileObject, V2PostSmsRequestModel
from app.legacy.v2.notifications.utils import (
    create_notification,
    enqueue_notification_tasks,
    get_arn_from_icn,
    send_push_notification_helper,
    validate_push_template,
    validate_template,
    validate_template_personalisation,
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
        template = await sample_template(template_type=NotificationType.SMS)

        with patch(
            'app.legacy.v2.notifications.utils.LegacyTemplateDao.get_by_id_and_service_id', return_value=template
        ):
            # validate_template either runs successfully or raises an exception
            await validate_template(template.id, template.service_id, NotificationType.SMS)

    async def test_validate_template_raises_exception_when_template_not_active(
        self,
        sample_template: Callable[..., Awaitable[Row[Any]]],
    ) -> None:
        """Test validate_template raises an exception when the template is not active."""
        template = await sample_template(archived=True, template_type=NotificationType.SMS)

        with patch(
            'app.legacy.v2.notifications.utils.LegacyTemplateDao.get_by_id_and_service_id', return_value=template
        ):
            with pytest.raises(HTTPException) as exc_info:
                await validate_template(template.id, uuid4(), NotificationType.SMS)

            assert exc_info.value.detail == 'Template has been deleted'

    async def test_validate_template_raises_exception_when_service_id(self) -> None:
        """Test validate_template raises an exception when the template is not found."""
        with patch(
            'app.legacy.v2.notifications.utils.LegacyTemplateDao.get_by_id_and_service_id',
            side_effect=NonRetryableError('Template not found'),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await validate_template(
                    uuid4(),
                    uuid4(),
                    NotificationType.SMS,
                )
            assert exc_info.value.detail == 'Template not found'

    async def test_validate_template_raises_exception_when_template_not_expected_type(
        self,
        sample_template: Callable[..., Awaitable[Row[Any]]],
    ) -> None:
        """Test validate_template raises an exception when the template is not the expected type."""
        template = await sample_template(template_type=NotificationType.EMAIL)

        with patch(
            'app.legacy.v2.notifications.utils.LegacyTemplateDao.get_by_id_and_service_id', return_value=template
        ):
            with pytest.raises(HTTPException) as exc_info:
                await validate_template(template.id, uuid4(), NotificationType.SMS)
            assert exc_info.value.detail == (
                f'{NotificationType.EMAIL} template is not suitable for {NotificationType.SMS} notification'
            )


class TestValidateTemplatePersonalisation:
    """Test validate_template_personalisation."""

    async def test_validate_template_personalisation_happy_path(
        self, sample_template: Callable[..., Awaitable[Row[Any]]]
    ) -> None:
        """Test validate_template_personalisation for happy path."""
        template = await sample_template(content='before ((content)) after')
        personalisation = cast(
            dict[str, str | int | float | list[str | int | float] | PersonalisationFileObject],
            {'content': 'test content'},
        )

        # Should not raise an exception
        validate_template_personalisation(template, personalisation)

    async def test_validate_template_personalisation_raises_exception_when_missing_personalisation(
        self, sample_template: Callable[..., Awaitable[Row[Any]]]
    ) -> None:
        """Test validate_template raises an exception when personalisation is missing."""
        template = await sample_template(content='before ((content)) after')
        with pytest.raises(HTTPException, match='Missing personalisation: content'):
            validate_template_personalisation(template, {'foo': 'bar'})


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
    mocker.patch('app.legacy.v2.notifications.utils.LegacyNotificationDao.create_notification')
    mocker.patch('app.legacy.v2.notifications.route_schema.LegacyServiceSmsSenderDao.get_service_default')
    mock_context = mocker.patch('app.legacy.v2.notifications.utils.context')
    mock_context['api_key_id'] = uuid4()
    mock_context['service_id'] = uuid4()
    mocker.patch('app.legacy.v2.notifications.route_schema.context', return_value=mock_context)

    request = V2PostSmsRequestModel(phone_number='+18005550101', template_id=uuid4())
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
    mocker.patch('app.legacy.v2.notifications.route_schema.LegacyServiceSmsSenderDao.get_service_default')
    mock_context = mocker.patch('app.legacy.v2.notifications.utils.context')
    mock_context['api_key_id'] = uuid4()
    mock_context['service_id'] = uuid4()
    mocker.patch('app.legacy.v2.notifications.route_schema.context', return_value=mock_context)

    with pytest.raises(HTTPException) as exc_info:
        await create_notification(uuid4(), mocker.AsyncMock(), request)
    assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert exc_info.value.detail == RESPONSE_500
