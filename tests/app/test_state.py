"""Test for ENPState Module."""

from app.providers.provider_aws import ProviderAWS
from app.state import ENPState


def test_enp_state_initialization() -> None:
    """Test to make sure ENPState can have provider attribute."""
    state = ENPState()
    state.providers = {'aws': ProviderAWS()}
    assert 'aws' in state.providers
    assert isinstance(state.providers['aws'], ProviderAWS)


def test_clear_providers() -> None:
    """Test the clear_providers method to ensure it clears the providers dictionary."""
    state = ENPState()

    assert len(state.providers) == 1
    state.clear_providers()
    assert len(state.providers) == 0
