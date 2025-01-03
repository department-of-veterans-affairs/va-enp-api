"""Fixtures and setup to test the app."""

import base64
import hmac
import json
import time
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

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
            'Authorization': f'Bearer {self.get_jwt_token(self.client_id, self.client_secret)}',
        }
        super().__init__(app, headers=headers)

    def get_jwt_token(cls, client_id: str, client_secret: str) -> str:
        """Utility to generate a JWT token.

        Args:
            client_id (str): Client ID
            client_secret (str): Client secret

        Returns:
            str: a signed JWT token
        """
        header_dict = {'typ': 'JWT', 'alg': 'HS256'}
        header = json.dumps(header_dict)
        current_timestamp = int(time.time())
        payload_dict = {
            'iss': client_id,
            'iat': current_timestamp,
            'exp': current_timestamp + cls.token_expiry,
            'jti': 'jwt_nonce',
        }
        payload = json.dumps(payload_dict)

        header = base64.urlsafe_b64encode(bytes(str(header), 'utf-8')).decode().replace('=', '')
        payload = base64.urlsafe_b64encode(bytes(str(payload), 'utf-8')).decode().replace('=', '')

        signature = hmac.new(
            bytes(client_secret, 'utf-8'), bytes(header + '.' + payload, 'utf-8'), digestmod='sha256'
        ).digest()
        sigb64 = base64.urlsafe_b64encode(bytes(signature)).decode().replace('=', '')

        token = header + '.' + payload + '.' + sigb64
        return token


@pytest.fixture(scope='session')
def client() -> ENPTestClient:
    """Return a test client.

    Returns:
        ENPTestClient: A test client to test with

    """
    app.enp_state = ENPState()

    app.enp_state.providers['aws'] = Mock(spec=ProviderAWS)

    return ENPTestClient(app)
