"""Fixtures and setup to test the app."""

from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.main import CustomFastAPI, app
from app.providers.provider_aws import ProviderAWS
from app.state import ENPState


class EnpTestClient(TestClient):
    """An ENP test client for the CustomFastAPI app.

    Args:
        TestClient (TestClient): FastAPI's test client.
    """

    app: CustomFastAPI


@pytest.fixture(scope='session')
def client() -> EnpTestClient:
    """Return a test client.

    Returns:
        EnpTestClient: A test client to test with

    """
    app.enp_state = ENPState()

    app.enp_state.providers['aws'] = Mock(spec=ProviderAWS)

    return EnpTestClient(app)
