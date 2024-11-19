"""Test cases for the device-registrations REST API."""

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.v3.device_registrations.route_schema import DeviceRegistrationSingleRequest


# Valid applications are VA_FLAGSHIP_APP, VETEXT.  Valid platforms are IOS, ANDROID.
@pytest.mark.parametrize(
    ('application', 'platform'),
    [
        ('VA_FLAGSHIP_APP', 'IOS'),
        ('VA_FLAGSHIP_APP', 'ANDROID'),
        ('VETEXT', 'IOS'),
        ('VETEXT', 'ANDROID'),
    ],
)
def test_post(client: TestClient, application: str, platform: str) -> None:
    """Test POST /v3/device-registration.

    The endpoint should return a 201 status code, and the response should include
    the endpoint sid.

    Args:
        client(TestClient): FastAPI client fixture
        application(str): The application name, either VA_FLAGSHIP_APP or VETEXT
        platform(str): The platform name, either IOS or ANDROID

    """
    if hasattr(client.app, 'state'):
        client.app.state.providers['aws'].register_device.return_value = 'arn:aws:sns:endpoint_sid'

    request = DeviceRegistrationSingleRequest(
        device_name='test',
        device_token='test',
        app_name=application,
        os_name=platform,
    )
    resp = client.post('v3/device-registrations', json=request.model_dump())
    assert resp.status_code == status.HTTP_201_CREATED
    assert 'endpoint_sid' in resp.json()


def test_post_with_camel_casing(client: TestClient) -> None:
    """Test POST /v3/device-registration with camel casing.

    Args:
        client(TestClient): FastAPI client fixture

    """
    if hasattr(client.app, 'state'):
        client.app.state.providers['aws'].register_device.return_value = 'arn:aws:sns:endpoint_sid'

    request = {
        'deviceName': 'test',
        'deviceToken': 'test',
        'appName': 'VETEXT',
        'osName': 'IOS',
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
        client(TestClient): FastAPI client fixture
        request_json(dict): JSON request, from the parametrize decorator

    """
    resp = client.post('v3/device-registrations', json=request_json)
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
