"""Test module for app/legacy/v2/notifications/utils.py."""

from typing import Any, Awaitable, Callable
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from pytest_mock.plugin import MockerFixture
from sqlalchemy import Row
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import NotificationType
from app.exceptions import NonRetryableError, RetryableError
from app.legacy.v2.notifications.utils import (
    _validate_template_active,
    _validate_template_service,
    _validate_template_type,
    get_arn_from_icn,
    get_template_cache,
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

    async def test_validate_template(
        self, sample_template: Callable[..., Awaitable[Row[Any]]], sample_service: Callable[..., Awaitable[Row[Any]]]
    ) -> None:
        """Test validate_template for happy path."""
        service = await sample_service()
        service_id = service.id
        template = await sample_template(service_id=service_id)

        with patch(
            'app.legacy.v2.notifications.utils.get_template_cache', new_callable=AsyncMock, return_value=template
        ):
            # validate_template either runs successfully or raises an exception
            await validate_template(template.id, NotificationType.SMS, service_id)

    async def test_validate_template_raises_exception_when_template_not_found(self) -> None:
        """Test validate_template raises an exception when the template is not found."""
        service_id = uuid4()

        with patch(
            'app.legacy.v2.notifications.utils.get_template_cache',
            side_effect=NonRetryableError(log_msg='Template not found'),
        ):
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

        with patch(
            'app.legacy.v2.notifications.utils.get_template_cache', new_callable=AsyncMock, return_value=template
        ):
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

        with patch(
            'app.legacy.v2.notifications.utils.get_template_cache', new_callable=AsyncMock, return_value=template
        ):
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

        with patch(
            'app.legacy.v2.notifications.utils.get_template_cache', new_callable=AsyncMock, return_value=template
        ):
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

    async def test_validate_template_personalisation_success(
        self, sample_template: Callable[..., Awaitable[Row[Any]]]
    ) -> None:
        """Test validate_template_personalisation for happy path."""
        template = await sample_template()
        template_id = template.id
        # Create a mock template with content attribute
        mock_template = AsyncMock()
        mock_template.content = 'Hello ((content))'

        with patch(
            'app.legacy.v2.notifications.utils.get_template_cache', new_callable=AsyncMock, return_value=mock_template
        ):
            # Should run successfully without raising an exception
            await validate_template_personalisation(template_id, {'content': 'test content'})

    async def test_validate_template_personalisation_case_insensitive(self) -> None:
        """Test validate_template_personalisation handles case insensitive matching."""
        template_id = uuid4()
        mock_template = AsyncMock()
        mock_template.content = 'before ((Content)) after'

        with patch(
            'app.legacy.v2.notifications.utils.get_template_cache', new_callable=AsyncMock, return_value=mock_template
        ):
            # Should run successfully with different case
            await validate_template_personalisation(template_id, {'content': 'test content'})

    async def test_validate_template_personalisation_no_personalisation_required(self) -> None:
        """Test validate_template_personalisation when no personalisation is required."""
        template_id = uuid4()
        mock_template = AsyncMock()
        mock_template.content = 'simple message with no placeholders'

        with patch(
            'app.legacy.v2.notifications.utils.get_template_cache', new_callable=AsyncMock, return_value=mock_template
        ):
            # Should run successfully with no personalisation
            await validate_template_personalisation(template_id, None)

    async def test_validate_template_personalisation_raises_exception_when_missing_personalisation(self) -> None:
        """Test validate_template_personalisation raises an exception when personalisation is missing."""
        template_id = uuid4()
        mock_template = AsyncMock()
        mock_template.content = 'before ((content)) after'

        with patch(
            'app.legacy.v2.notifications.utils.get_template_cache', new_callable=AsyncMock, return_value=mock_template
        ):
            with pytest.raises(NonRetryableError) as error:
                await validate_template_personalisation(template_id, {})

            assert 'Missing personalisation: content' in str(error.value.log_msg)

    async def test_validate_template_personalisation_raises_exception_when_partially_missing(self) -> None:
        """Test validate_template_personalisation raises an exception when some personalisation is missing."""
        template_id = uuid4()
        mock_template = AsyncMock()
        mock_template.content = 'Hello ((name)), your ((item)) is ready'

        with patch(
            'app.legacy.v2.notifications.utils.get_template_cache', new_callable=AsyncMock, return_value=mock_template
        ):
            with pytest.raises(NonRetryableError) as error:
                await validate_template_personalisation(template_id, {'name': 'John'})

            assert 'Missing personalisation: item' in str(error.value.log_msg)


@pytest.mark.skip(reason='TODO #134: cache not working with async')
class TestGetTemplateCache:
    """Test get_template_cache function."""

    async def test_get_template_cache_success(
        self, test_db_session: AsyncSession, sample_template: Callable[..., Awaitable[Row[Any]]]
    ) -> None:
        """Test get_template_cache for happy path."""
        template = await sample_template(session=test_db_session)
        await test_db_session.commit()

        template_id = template.id

        result = await get_template_cache(template_id)

        assert result.id == template_id

    async def test_get_template_cache_raises_exception_when_template_not_found(self) -> None:
        """Test get_template_cache raises exception when template not found."""
        non_existent_template_id = uuid4()

        with pytest.raises((NonRetryableError, RetryableError)):
            await get_template_cache(non_existent_template_id)

    async def test_get_template_cache_caching_behavior(
        self,
        test_db_session: AsyncSession,
        sample_template: Callable[..., Awaitable[Row[Any]]],
        mocker: MockerFixture,
    ) -> None:
        """Test get_template_cache caching behavior."""
        template = await sample_template(session=test_db_session)
        await test_db_session.commit()
        template_id = template.id

        db_spy = mocker.spy(test_db_session, 'execute')

        # First call - should hit the DAO
        result1 = get_template_cache(template_id)
        assert db_spy.call_count == 1
        result_1 = result1.id
        # Second call - should use cached result, DAO call count does not increase
        result2 = get_template_cache(template_id)
        assert db_spy.call_count == 1
        result_2 = result2.id

        assert result_1 == result_2


class TestValidateTemplateService:
    """Test _validate_template_service function."""

    def test_validate_template_service_success(self) -> None:
        """Test _validate_template_service for happy path when service IDs match."""
        service_id = uuid4()
        template_id = uuid4()

        # Should not raise any exception when service IDs match
        _validate_template_service(service_id, service_id, template_id)

    def test_validate_template_service_raises_exception_when_service_mismatch(self) -> None:
        """Test _validate_template_service raises exception when service IDs don't match."""
        template_service_id = uuid4()
        expected_service_id = uuid4()
        template_id = uuid4()

        with pytest.raises(NonRetryableError) as error:
            _validate_template_service(template_service_id, expected_service_id, template_id)

        assert 'Template does not belong to the specified service' in str(error.value.log_msg)

    @patch('app.legacy.v2.notifications.utils.logger.warning')
    def test_validate_template_service_logs_warning_on_mismatch(self, mock_logger: AsyncMock) -> None:
        """Test _validate_template_service logs warning when service IDs don't match."""
        template_service_id = uuid4()
        expected_service_id = uuid4()
        template_id = uuid4()

        with pytest.raises(NonRetryableError):
            _validate_template_service(template_service_id, expected_service_id, template_id)

        mock_logger.assert_called_once()
