"""Tests for the authentication module."""

import base64
import hmac
import json
import time
from typing import TypedDict
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient


class PayloadDict(TypedDict):
    """Payload dictionary type."""

    iat: int
    exp: int
    jti: str


def _get_jwt_token(client_secret: str, payload_dict: PayloadDict) -> str:
    """Utility to generate a JWT token.

    Args:
        client_secret (str): Client secret
        payload_dict (dict[str, str]): Payload dictionary

    Returns:
        str: a signed JWT token
    """
    header_dict = {'typ': 'JWT', 'alg': 'HS256'}
    header = json.dumps(header_dict)
    payload = json.dumps(payload_dict)

    header = base64.urlsafe_b64encode(bytes(str(header), 'utf-8')).decode().replace('=', '')
    payload = base64.urlsafe_b64encode(bytes(str(payload), 'utf-8')).decode().replace('=', '')

    signature = hmac.new(
        bytes(client_secret, 'utf-8'), bytes(header + '.' + payload, 'utf-8'), digestmod='sha256'
    ).digest()
    sigb64 = base64.urlsafe_b64encode(bytes(signature)).decode().replace('=', '')

    token = header + '.' + payload + '.' + sigb64
    return token


def test_credentials_returns_none(client: TestClient, mocker: AsyncMock) -> None:
    """Test when the credentials call returns None.

    Args:
        client (TestClient): FastAPI test client
        mocker: Pytest mocker
    """
    mocker.patch('app.auth.HTTPBearer.__call__', return_value=None)
    response = client.post('/v3/device-registrations')
    assert response.status_code == 403
    assert response.json() == {'detail': 'Not authenticated'}


def test_missing_authorization_scheme(client: TestClient) -> None:
    """Test the invalid(missing) authorization scheme.

    Args:
        client (TestClient): FastAPI test client
    """
    client_secret = 'not-very-secret'
    current_timestamp = int(time.time())
    payload_dict: PayloadDict = {
        'iat': current_timestamp,
        'exp': current_timestamp + 60,
        'jti': 'jwt_nonce',
    }
    response = client.post(
        '/v3/device-registrations', headers={'Authorization': f'{_get_jwt_token(client_secret, payload_dict)}'}
    )
    assert response.status_code == 403
    assert response.json() == {'detail': 'Not authenticated'}


def test_expired_iat_in_token(client: TestClient) -> None:
    """Test an expired iat in token.

    Args:
        client (TestClient): FastAPI test client
    """
    client_secret = 'not-very-secret'
    current_timestamp = int(time.time())
    payload_dict: PayloadDict = {
        'iat': current_timestamp - 300,
        'exp': current_timestamp - 240,
        'jti': 'jwt_nonce',
    }
    response = client.post(
        '/v3/device-registrations', headers={'Authorization': f'Bearer {_get_jwt_token(client_secret, payload_dict)}'}
    )
    assert response.status_code == 403
    assert response.json() == {'detail': 'Invalid token or expired token.'}


def test_future_iat_in_token(client: TestClient) -> None:
    """Test an iat in the future in token.

    Args:
        client (TestClient): FastAPI test client
    """
    client_secret = 'not-very-secret'
    current_timestamp = int(time.time())
    payload_dict: PayloadDict = {
        'iat': current_timestamp + 120,
        'exp': current_timestamp + 180,
        'jti': 'jwt_nonce',
    }
    response = client.post(
        '/v3/device-registrations', headers={'Authorization': f'Bearer {_get_jwt_token(client_secret, payload_dict)}'}
    )
    assert response.status_code == 403
    assert response.json() == {'detail': 'Invalid token or expired token.'}
