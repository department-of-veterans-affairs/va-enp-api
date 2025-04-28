"""Tests for the VA Profile client."""

from app.clients.va_profile import register_device_with_vaprofile
from app.constants import MobileAppType, OSPlatformType


class TestRegisterDeviceWithVAProfile:
    """Tests for the register_device_with_vaprofile function."""

    def test_register_device_returns_true(self) -> None:
        """Test that register_device_with_vaprofile returns True."""
        result = register_device_with_vaprofile(
            endpoint_sid='test-endpoint-sid',
            device_name='test-device',
            device_os=OSPlatformType.IOS,
            app_name=MobileAppType.VA_FLAGSHIP_APP,
            token='test-token',
        )
        assert result is True
