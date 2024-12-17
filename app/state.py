from typing import Any, Dict

from app.providers.provider_aws import ProviderAWS


class ENPState:
    """Custom application state class to hold providers."""

    def __init__(self) -> None:
        self.providers: Dict[str, Any] = {'aws': ProviderAWS()}

    def clear_providers(self) -> None:
        """Clear the providers dictionary."""
        self.providers.clear()
