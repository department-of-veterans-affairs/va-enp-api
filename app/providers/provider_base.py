"""Base class for Providers."""

from abc import ABC

from loguru import logger
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_full_jitter

from app.constants import MAX_RETRIES
from app.exceptions import NonRetryableError, RetryableError
from app.providers.provider_schemas import PushModel
from app.utils import log_last_attempt_on_failure, log_on_retry


class ProviderBase(ABC):
    """Abstract base class for all providers."""

    # id: key
    credentials: dict[str, str]

    def __init__(self) -> None:
        """Log instantiations."""
        logger.info('Initialized provider class {}.', type(self).__name__)

    async def process_response(self) -> None:
        """Process the asynchronous response from a provider.

        Facilitates update and log consistency regardless of response.
        """
        raise NotImplementedError(f'Derived class: {self.__class__.__name__} does not implement this method.')

    @retry(
        before_sleep=log_on_retry,
        reraise=True,
        retry_error_callback=log_last_attempt_on_failure,
        retry=retry_if_exception_type(RetryableError),
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_full_jitter(multiplier=1, max=60),
    )
    async def send_notification(self, model: PushModel) -> str:
        """Send a notification using the provider.

        Facilitates update and log consistency regardless of notification.

        Args:
            model (PushModel): the parameters to pass to SNS.Client.publish

        Raises:
            NonRetryableError: Don't retry the request

        Returns:
            str: A reference identifier for the sent notification

        """
        try:
            return await self._send_push(model)
        except NonRetryableError:
            logger.exception(
                'Sending a push notification failed for {} {}.',
                'TargetArn' if (model.target_arn is not None) else 'TopicArn',
                model.target_arn or model.topic_arn,
            )
            raise

    async def _process_email_response(self) -> None:
        """Process an email response from this provider."""
        raise NotImplementedError(f'Derived class: {self.__class__.__name__} does not implement this method.')

    async def _process_push_response(self) -> None:
        """Process a push response from this provider."""
        raise NotImplementedError(f'Derived class: {self.__class__.__name__} does not implement this method.')

    async def _process_sms_response(self) -> None:
        """Process a sms response from this provider."""
        raise NotImplementedError(f'Derived class: {self.__class__.__name__} does not implement this method.')

    async def _send_email(self) -> str:
        """Send an email request to this provider.  Return a reference string."""
        raise NotImplementedError(f'Derived class: {self.__class__.__name__} does not implement this method.')

    async def _send_push(self, push_model: PushModel) -> str:
        """Send a push request to this provider.

        Return a reference string.

        Args:
            push_model: the parameters to pass to SNS.Client.publish

        Returns:
            str: A reference identifier for the sent notification

        """
        raise NotImplementedError(f'Derived class: {self.__class__.__name__} does not implement this method.')

    async def _send_sms(self) -> str:
        """Send a sms request to this provider.  Return a reference string."""
        raise NotImplementedError(f'Derived class: {self.__class__.__name__} does not implement this method.')
