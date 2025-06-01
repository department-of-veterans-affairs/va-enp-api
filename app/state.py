"""This module manages state for the application."""

from typing import Dict

from app.clients.redis_client import RedisClientManager
from app.providers.provider_aws import ProviderAWS
from app.providers.provider_base import ProviderBase


class ENPState:
    """Custom application state class."""

    def __init__(self) -> None:
        """Initialize ENPState with a default set of providers."""
        # Route handlers should access this dictionary to send notifications using
        # various third-party services, such as AWS, Twilio, etc.
        self.providers: Dict[str, ProviderBase] = {'aws': ProviderAWS()}
        self.redis_client: RedisClientManager | None = None

    def clear_providers(self) -> None:
        """Clear the providers dictionary."""
        self.providers.clear()
