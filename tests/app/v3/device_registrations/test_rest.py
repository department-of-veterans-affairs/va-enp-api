from unittest import mock

from fastapi.testclient import TestClient
from fastapi import status

import pytest

from app.v3.device_registrations.route_schema import DeviceRegistrationSingleRequest


def test_post(client: TestClient) -> None:
    """Test POST /v3/device-registration.

    The endpoint should return a 201 status code, and the response should include
    the endpoint sid.

    Args:
    ----
        client(TestClient): FastAPI client fixture

    """
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
def test_post_missing_data(client: TestClient, request_json) -> None:
    """Test POST /v3/device-registration with missing data.

    The endpoint should return a 400 status code.

    Args:
    ----
        client(TestClient): FastAPI client fixture

    """
    resp = client.post('v3/device-registrations', json=request_json)
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


def test_post_aws_provider_register_device(client: TestClient) -> None:
    """Ensure that the AWS provider's register_device method is called.

    Args:
    ----
        client(TestClient): FastAPI client fixture

    """
    request = DeviceRegistrationSingleRequest(
        device_name='test',
        device_token='test',
        app_name='test',
        os_name='test',
    )
    with mock.patch('app.providers.provider_aws.ProviderAWS.register_device') as mock_register_device:
        client.post('v3/device-registrations', json=request.model_dump())

    mock_register_device.assert_called_once()