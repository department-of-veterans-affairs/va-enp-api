"""Test cases for the device-registrations REST API."""

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.constants import MobileAppType, OSPlatformType
from app.v3.device_registrations.route_schema import DeviceRegistrationRequest


# Valid applications are VA_FLAGSHIP_APP, VETEXT.  Valid platforms are IOS, ANDROID.
@pytest.mark.parametrize(
    ('application', 'platform', 'payload'),
    [
        ('VA_FLAGSHIP_APP', 'IOS', {'device_name': 'test', 'device_token': 'test'}),
        ('VA_FLAGSHIP_APP', 'ANDROID', {'deviceName': 'test', 'device_token': 'test'}),
        ('VETEXT', 'IOS', {'device_name': 'test', 'device_token': 'test'}),
        ('VETEXT', 'ANDROID', {'device_name': 'test', 'deviceToken': 'test'}),
    ],
    ids=[
        'VA_FLAGSHIP_APP_IOS',
        'VA_FLAGSHIP_APP_ANDROID',
        'VETEXT_IOS',
        'VETEXT_ANDROID',
    ],
)
def test_post(
    client: TestClient,
    application: MobileAppType,
    platform: OSPlatformType,
    payload: dict[str, str],
) -> None:
    """Test POST /v3/device-registration.

    The endpoint should return a 201 status code, and the response should include
    the endpoint sid.

    Args:
        client(TestClient): FastAPI client fixture
        application(str): The application name, either VA_FLAGSHIP_APP or VETEXT
        platform(str): The platform name, either IOS or ANDROID
        payload(dict): The request payload

    """
    client.app.state.providers[  # type: ignore
        'aws'
    ].register_device.return_value = (
        'arn:aws:sns:us-east-1:000000000000:endpoint/APNS/notify/00000000-0000-0000-0000-000000000000'
    )

    request = DeviceRegistrationRequest(**payload, app_name=application, os_name=platform)
    resp = client.post('v3/device-registrations', json=request.model_dump())
    assert resp.status_code == status.HTTP_201_CREATED
    assert resp.json()['endpoint_sid'] == '00000000-0000-0000-0000-000000000000'
