"""This module manages state for the application."""

from typing import Dict

from app.providers.provider_aws import ProviderAWS


class ENPState:
    """Custom application state class to hold providers."""

    def __init__(self) -> None:
        """Initialize ENPState with a default set of providers."""
        # Route handlers should access this dictionary to send notifications using
        # various third-party services, such as AWS, Twilio, etc.
        self.providers: Dict[str, ProviderAWS] = {'aws': ProviderAWS()}

    def clear_providers(self) -> None:
        """Clear the providers dictionary."""
        self.providers.clear()
