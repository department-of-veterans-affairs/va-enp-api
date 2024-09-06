"""Base class for Providers and provider exceptions."""

from abc import ABC


class ProviderRetryable(Exception):
    """Indicative of a retryable exception."""

    ...


class ProviderNonRetryable(Exception):
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

    async def send_notification(self) -> None:
        """Send a notification using the provider.

        Facilitates update and log consistency regardless of notification.
        """
        ...

    async def _process_email_response(self) -> None:
        """Send an email through this provider."""
        raise NotImplementedError(f'Derived class: {self.__class__.__name__} does not implement this method.')

    async def _process_push_response(self) -> None:
        """Send an push through this provider."""
        raise NotImplementedError(f'Derived class: {self.__class__.__name__} does not implement this method.')

    async def _process_sms_response(self) -> None:
        """Send an sms through this provider."""
        raise NotImplementedError(f'Derived class: {self.__class__.__name__} does not implement this method.')

    async def _send_email(self) -> str:
        """Send an email through this provider."""
        raise NotImplementedError(f'Derived class: {self.__class__.__name__} does not implement this method.')

    async def _send_push(self) -> str:
        """Send an push through this provider."""
        raise NotImplementedError(f'Derived class: {self.__class__.__name__} does not implement this method.')

    async def _send_sms(self) -> str:
        """Send an sms through this provider."""
        raise NotImplementedError(f'Derived class: {self.__class__.__name__} does not implement this method.')
