"""Fixtures and setup to test the app."""

from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.providers.provider_aws import ProviderAWS
from app.state import ENPState


@pytest.fixture(scope='session')
def client() -> TestClient:
    """Return a test client.

    Returns:
        TestClient: A test client to test with

    """
    app.enp_state = ENPState()
    app.enp_state.providers['aws'] = Mock(spec=ProviderAWS)
    return TestClient(app)
