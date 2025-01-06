"""Fixtures and setup to test the app."""

import os
import time
from unittest.mock import Mock

import jwt
import pytest
from fastapi.testclient import TestClient

from app.auth import JWTPayloadDict
from app.main import CustomFastAPI, app
from app.providers.provider_aws import ProviderAWS
from app.state import ENPState

ADMIN_SECRET_KEY = os.getenv('ENP_ADMIN_SECRET_KEY', 'not-very-secret')
ALGORITHM = os.getenv('ENP_ALGORITHM', 'HS256')
ACCESS_TOKEN_EXPIRE_SECONDS = int(os.getenv('ENP_ACCESS_TOKEN_EXPIRE_SECONDS', 60))


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


def generate_token(sig_key: str = ADMIN_SECRET_KEY, payload: JWTPayloadDict | None = None) -> str:
    """Generate a JWT token.

    Args:
        sig_key (str): The key to sign the JWT token with.
        payload (JWTPayloadDict): The payload to include in the JWT token.

    Returns:
        str: The signed JWT token.
    """
    headers = {
        'typ': 'JWT',
        'alg': ALGORITHM,
    }
    if payload is None:
        payload = JWTPayloadDict(
            iss='enp',
            iat=int(time.time()),
            exp=int(time.time()) + ACCESS_TOKEN_EXPIRE_SECONDS,
        )
    return jwt.encode(dict(payload), sig_key, headers=headers)
