"""Fixtures and setup to test the app."""

from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import app
from app.providers.provider_aws import ProviderAWS


class EnpTestClient(TestClient):
    """An ENP test client.

    This was implemented to avoid issues with MyPy not recognizing state attributes.

    Args:
        TestClient(TestClient): Starlette test client for FastAPI
    """

    app: FastAPI


@pytest.fixture(scope='session')
def client() -> EnpTestClient:
    """Return a custom test client.

    Returns:
        EnpTestClient: A custom test client to test with

    """
    app.state.providers = {'aws': Mock(spec=ProviderAWS)}
    return EnpTestClient(app)
