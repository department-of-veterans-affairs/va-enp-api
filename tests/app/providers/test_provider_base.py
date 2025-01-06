"""Test module for app/providers/provider_base.py."""

import pytest
from tenacity import stop_after_attempt, wait_none

from app.providers.provider_base import ProviderBase, ProviderNonRetryableError, ProviderRetryableError
from app.providers.provider_schemas import PushModel


async def test_not_implemented_virtual_void() -> None:
    """Ensure all methods that may be implmented raise an exception if they are not yet implemented."""

    class TestProviderDerived(ProviderBase): ...

    derived = TestProviderDerived()

    # Test each "virtual void" method
    with pytest.raises(NotImplementedError):
        await derived._process_email_response()
    with pytest.raises(NotImplementedError):
        await derived._process_push_response()
    with pytest.raises(NotImplementedError):
        await derived._process_sms_response()
    with pytest.raises(NotImplementedError):
        await derived._send_email()
    with pytest.raises(NotImplementedError):
        await derived._send_push(PushModel(message='', target_arn=''))
    with pytest.raises(NotImplementedError):
        await derived._send_sms()
    with pytest.raises(NotImplementedError):
        await derived.process_response()


class TestSendNotification:
    """Test the send_notification method of the ProviderBase class."""

    async def test_send_notification_success(self) -> None:
        """Test send_notification method when _send_push succeeds."""

        class TestProviderDerived(ProviderBase):
            async def _send_push(self, model: PushModel) -> str:
                return 'success'

        derived = TestProviderDerived()
        model = PushModel(message='test', target_arn='test-arn')

        result = await derived.send_notification(model)
        assert result == 'success'

    async def test_send_notification_retryable_error(self) -> None:
        """Test send_notification method when _send_push raises a retryable error."""

        class TestProviderDerived(ProviderBase):
            async def _send_push(self, model: PushModel) -> str:
                raise ProviderRetryableError('Retryable error')

        derived = TestProviderDerived()
        model = PushModel(message='test', target_arn='test-arn')

        # Using retry_with is necessary to avoid performing retries with the default wait strategy.
        assert (
            await derived.send_notification.retry_with(stop=stop_after_attempt(2), wait=wait_none())(derived, model)  # type: ignore
            is None
        )

    async def test_send_notification_non_retryable_error(self) -> None:
        """Test send_notification method when _send_push raises a non-retryable error."""

        class TestProviderDerived(ProviderBase):
            async def _send_push(self, model: PushModel) -> str:
                raise ProviderNonRetryableError('Non-retryable error')

        derived = TestProviderDerived()
        model = PushModel(message='test', target_arn='test-arn')

        with pytest.raises(ProviderNonRetryableError):
            await derived.send_notification(model)

    async def test_send_notification_retries(self) -> None:
        """Test send_notification method retries on retryable error."""

        class TestProviderDerived(ProviderBase):
            async def _send_push(self, model: PushModel) -> str:
                if not hasattr(self, 'attempt'):
                    self.attempt = 0
                self.attempt += 1
                if self.attempt < 3:
                    raise ProviderRetryableError('Retryable error')
                return 'success'

        derived = TestProviderDerived()
        model = PushModel(message='test', target_arn='test-arn')

        # Using retry_with is necessary to avoid performing retries with the default wait strategy.
        result = await derived.send_notification.retry_with(stop=stop_after_attempt(3), wait=wait_none())(  # type: ignore
            derived, model
        )
        assert result == 'success'
        assert derived.attempt == 3
