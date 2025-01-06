"""Tests for the authentication module."""

import time
from unittest.mock import AsyncMock
from uuid import uuid4

from fastapi import status
from fastapi.testclient import TestClient

from app.auth import JWTPayloadDict, generate_token


def test_happy_path(client: TestClient) -> None:
    """Test that the endpoint returns a 200 status code, with valid credentials provided by the test client.

    Args:
        client(ENPTestClient): Custom FastAPI client fixture
    """
    resp = client.get(f'/v3/notifications/{uuid4()}')
    assert resp.status_code == status.HTTP_200_OK


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
    response = client.post('/v3/device-registrations', headers={'Authorization': f'{generate_token()}'})
    assert response.status_code == 403
    assert response.json() == {'detail': 'Not authenticated'}


def test_expired_iat_in_token(client: TestClient) -> None:
    """Test an expired iat in token.

    Args:
        client (TestClient): FastAPI test client
    """
    current_timestamp = int(time.time())
    payload: JWTPayloadDict = {
        'iss': 'enp',
        'iat': current_timestamp - 300,
        'exp': current_timestamp - 240,
    }
    response = client.post(
        '/v3/device-registrations', headers={'Authorization': f'Bearer {generate_token(payload=payload)}'}
    )
    assert response.status_code == 403
    assert response.json() == {'detail': 'Invalid token or expired token.'}


def test_future_iat_in_token(client: TestClient) -> None:
    """Test an iat in the future in token.

    Args:
        client (TestClient): FastAPI test client
    """
    current_timestamp = int(time.time())
    payload: JWTPayloadDict = {
        'iss': 'enp',
        'iat': current_timestamp + 120,
        'exp': current_timestamp + 180,
    }
    response = client.post(
        '/v3/device-registrations', headers={'Authorization': f'Bearer {generate_token(payload=payload)}'}
    )
    assert response.status_code == 403
    assert response.json() == {'detail': 'Invalid token or expired token.'}
