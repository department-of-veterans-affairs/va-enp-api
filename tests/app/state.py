from app.providers.provider_aws import ProviderAWS
from app.state import ENPState


def test_enp_state_initialization():
    state = ENPState()
    state.providers = {'aws': ProviderAWS()}
    assert 'aws' in state.providers
    assert isinstance(state.providers['aws'], ProviderAWS)
