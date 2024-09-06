"""Fixtures and setup to test the app."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope='session')
def client() -> TestClient:
    """Return a test client.

    Returns
    -------
        TestClient: A test client to test with

    """
    return TestClient(app)
