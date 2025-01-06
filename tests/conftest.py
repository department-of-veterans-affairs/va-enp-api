"""Fixtures and setup to test the app."""

from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.auth import generate_token
from app.main import CustomFastAPI, app
from app.providers.provider_aws import ProviderAWS
from app.state import ENPState


class ENPTestClient(TestClient):
    """An ENP test client for the CustomFastAPI app.

    Args:
        TestClient (TestClient): FastAPI's test client.
    """

    app: CustomFastAPI
    token_expiry = 60
    client_id = 'test'
    client_secret = 'not-very-secret'

    def __init__(self, app: CustomFastAPI) -> None:
        """Initialize the ENPTestClient.

        Args:
            app (CustomFastAPI): The FastAPI application instance.
        """
        headers = {
            'Authorization': f'Bearer {generate_token()}',
        }
        super().__init__(app, headers=headers)


@pytest.fixture(scope='session')
def client() -> ENPTestClient:
    """Return a test client.

    Returns:
        ENPTestClient: A test client to test with

    """
    app.enp_state = ENPState()

    app.enp_state.providers['aws'] = Mock(spec=ProviderAWS)

    return ENPTestClient(app)
