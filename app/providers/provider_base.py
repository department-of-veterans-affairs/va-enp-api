"""Base class for Providers and provider exceptions."""

from abc import ABC

from loguru import logger

from app.providers.provider_schemas import PushModel


class ProviderRetryableError(Exception):
    """Indicative of a retryable exception."""

    ...


class ProviderNonRetryableError(Exception):
    """Indicative of a non-retryable exception."""

    ...


class ProviderBase(ABC):
    """Abstract base class for all providers."""

    # id: key
    credentials: dict[str, str]

    async def process_response(self) -> None:
        """Process the asynchronous response from a provider.

        Facilitates update and log consistency regardless of response.
        """
        ...

    async def send_notification(self, model: PushModel) -> str:
        """Send a notification using the provider.

        Facilitates update and log consistency regardless of notification.

        Raises
        ------
            ProviderNonRetryableError: Don't retry the request
            ProviderRetryableError: Retry the request

        Returns
        -------
            str: A reference identifier for the sent notification

        """
        try:
            return await self._send_push(model)
        except (ProviderRetryableError, ProviderNonRetryableError) as e:
            logger.exception(e)
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
        """Send a push request to this provider.  Return a reference string."""
        raise NotImplementedError(f'Derived class: {self.__class__.__name__} does not implement this method.')

    async def _send_sms(self) -> str:
        """Send a sms request to this provider.  Return a reference string."""
        raise NotImplementedError(f'Derived class: {self.__class__.__name__} does not implement this method.')
