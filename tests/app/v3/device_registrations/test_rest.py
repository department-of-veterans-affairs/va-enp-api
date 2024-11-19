"""Test cases for the device-registrations REST API."""

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.constants import MobileAppType, OSPlatformType
from app.v3.device_registrations.route_schema import DeviceRegistrationRequest


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
def test_post(client: TestClient, application: MobileAppType, platform: OSPlatformType) -> None:
    """Test POST /v3/device-registration.

    The endpoint should return a 201 status code, and the response should include
    the endpoint sid.

    Args:
        client(TestClient): FastAPI client fixture
        application(str): The application name, either VA_FLAGSHIP_APP or VETEXT
        platform(str): The platform name, either IOS or ANDROID

    """
    if hasattr(client.app, 'state'):
        client.app.state.providers[
            'aws'
        ].register_device.return_value = (
            'arn:aws:sns:us-east-1:000000000000:endpoint/APNS/notify/00000000-0000-0000-0000-000000000000'
        )

    request = DeviceRegistrationRequest(
        device_name='test',
        device_token='test',
        app_name=application,
        os_name=platform,
    )
    resp = client.post('v3/device-registrations', json=request.model_dump())
    assert resp.status_code == status.HTTP_201_CREATED
    assert resp.json()['endpoint_sid'] == '00000000-0000-0000-0000-000000000000'


def test_post_with_camel_casing(client: TestClient) -> None:
    """Test POST /v3/device-registration with camel casing.

    Args:
        client(TestClient): FastAPI client fixture

    """
    if hasattr(client.app, 'state'):
        client.app.state.providers[
            'aws'
        ].register_device.return_value = (
            'arn:aws:sns:us-east-1:000000000000:endpoint/APNS/notify/00000000-0000-0000-0000-000000000000'
        )

    request = {
        'deviceName': 'test',
        'deviceToken': 'test',
        'appName': 'VETEXT',
        'osName': 'IOS',
    }
    resp = client.post('v3/device-registrations', json=request)
    assert resp.status_code == status.HTTP_201_CREATED
