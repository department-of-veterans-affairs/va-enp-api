"""Test cases for the device-registrations REST API."""

from unittest import mock

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.v3.device_registrations.route_schema import DeviceRegistrationSingleRequest


def test_post(client: TestClient) -> None:
    """Test POST /v3/device-registration.

    The endpoint should return a 201 status code, and the response should include
    the endpoint sid.

    Args:
    ----
        client(TestClient): FastAPI client fixture

    """
    client.app.state.providers['aws'].register_device = mock.AsyncMock(return_value='arn:aws:sns:endpoint_sid')

    request = DeviceRegistrationSingleRequest(
        device_name='test',
        device_token='test',
        app_name='test',
        os_name='test',
    )
    resp = client.post('v3/device-registrations', json=request.model_dump())
    assert resp.status_code == status.HTTP_201_CREATED
    assert 'endpoint_sid' in resp.json()


def test_post_with_camel_casing(client: TestClient) -> None:
    """Test POST /v3/device-registration with camel casing.

    Args:
    ----
        client(TestClient): FastAPI client fixture

    """
    client.app.state.providers['aws'].register_device = mock.AsyncMock(return_value='arn:aws:sns:endpoint_sid')
    request = {
        'deviceName': 'test',
        'deviceToken': 'test',
        'appName': 'test',
        'osName': 'test',
    }
    resp = client.post('v3/device-registrations', json=request)
    assert resp.status_code == status.HTTP_201_CREATED


@pytest.mark.parametrize(
    'request_json',
    [
        {'device_name': 'test', 'device_token': 'test', 'app_name': 'test'},
        {'device_name': 'test', 'device_token': 'test', 'os_name': 'test'},
        {'device_name': 'test', 'app_name': 'test', 'os_name': 'test'},
        {'device_token': 'test', 'app_name': 'test', 'os_name': 'test'},
    ],
)
def test_post_missing_data(client: TestClient, request_json: dict[str, str]) -> None:
    """Test POST /v3/device-registration with missing data.

    The endpoint should return a 400 status code.

    Args:
    ----
        client(TestClient): FastAPI client fixture
        request_json(dict): JSON request, from the parametrize decorator

    """
    resp = client.post('v3/device-registrations', json=request_json)
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
