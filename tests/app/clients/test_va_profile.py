"""Tests for the VA Profile client."""

from unittest.mock import MagicMock, patch

import pytest

from app.clients.va_profile import get_contact_info, register_device_with_vaprofile
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


class TestGetContactInfo:
    """Tests for the get_contact_info function."""

    @pytest.mark.asyncio
    async def test_get_contact_info_success(self) -> None:
        """Test the happy path for get_contact_info."""
        # Test with a valid ICN format
        result = await get_contact_info('ICN', '1234567890V123456')

        # Check that the result contains expected fields with expected format
        assert 'email' in result
        assert 'phone_number' in result
        assert result['email'] == 'user-123456@example.com'
        assert result['phone_number'] == '+18005551456'

    @pytest.mark.asyncio
    async def test_get_contact_info_with_different_id_values(self) -> None:
        """Test get_contact_info with different ID values to verify deterministic results."""
        # Test with different ID value
        result1 = await get_contact_info('ICN', '9876543210V999888')
        assert result1['email'] == 'user-999888@example.com'
        assert result1['phone_number'] == '+18005551888'

        # Test with another ID value
        result2 = await get_contact_info('EDIPI', '1122334455')
        assert result2['email'] == 'user-334455@example.com'
        assert result2['phone_number'] == '+18005551455'

    @pytest.mark.asyncio
    async def test_get_contact_info_invalid_id(self) -> None:
        """Test get_contact_info with invalid ID (too short)."""
        # Test with short ID value
        with pytest.raises(ValueError, match='Invalid identifier value format') as exc_info:
            await get_contact_info('ICN', '123')
        assert 'Invalid identifier value format' in str(exc_info.value)

        # Test with empty ID value
        with pytest.raises(ValueError, match='Invalid identifier value format') as exc_info:
            await get_contact_info('ICN', '')
        assert 'Invalid identifier value format' in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_contact_info_user_not_found(self) -> None:
        """Test get_contact_info when user is not found (ID ends with '0000')."""
        with pytest.raises(ConnectionError, match='User with ICN not found') as exc_info:
            await get_contact_info('ICN', '1234567890V120000')
        assert 'User with ICN not found' in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_contact_info_connection_error(self) -> None:
        """Test get_contact_info when a connection error occurs."""
        # Patch asyncio.sleep to raise ConnectionError
        with patch('asyncio.sleep', side_effect=ConnectionError('Failed to connect')):
            with pytest.raises(ConnectionError, match='Failed to connect') as exc_info:
                await get_contact_info('ICN', '1234567890V123456')
            assert 'Failed to connect' in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_contact_info_unexpected_error(self) -> None:
        """Test get_contact_info when an unexpected error occurs."""
        # Patch asyncio.sleep to raise an unexpected error
        with patch('asyncio.sleep', side_effect=RuntimeError('Unexpected error')):
            with pytest.raises(ConnectionError, match='Error retrieving data from VA Profile') as exc_info:
                await get_contact_info('ICN', '1234567890V123456')
            assert 'Error retrieving data from VA Profile' in str(exc_info.value)
            assert 'Unexpected error' in str(exc_info.value)

    @pytest.mark.asyncio
    @patch('app.clients.va_profile.logger')
    async def test_logging_success(self, mock_logger: MagicMock) -> None:
        """Test successful logging in get_contact_info function."""
        # Test successful case
        await get_contact_info('ICN', '1234567890V123456')

        # Verify debug and info logging calls
        mock_logger.debug.assert_any_call(
            'Getting contact info from VA Profile for identifier type {} and value {}', 'ICN', '1234567890V123456'
        )
        mock_logger.info.assert_called_with('Successfully retrieved contact information for {}', '1234567890VXXXXXX')

    @pytest.mark.asyncio
    @patch('app.clients.va_profile.logger')
    async def test_logging_error(self, mock_logger: MagicMock) -> None:
        """Test error logging in get_contact_info function."""
        # Test error case
        with pytest.raises(ValueError, match="Invalid identifier value format for type 'ICN'"):
            await get_contact_info('ICN', '123')

        # Verify error logging calls
        mock_logger.error.assert_called_with('Invalid identifier value provided: too short')

    @pytest.mark.asyncio
    @patch('app.clients.va_profile.logger')
    async def test_logging_connection_error(self, mock_logger: MagicMock) -> None:
        """Test connection error logging in get_contact_info function."""
        # Test connection error case
        with patch('asyncio.sleep', side_effect=ConnectionError('Failed to connect')):
            with pytest.raises(ConnectionError, match='Failed to connect'):
                await get_contact_info('ICN', '1234567890V123456')

        # Verify error logging calls
        mock_logger.error.assert_called_with('Connection to VA Profile failed: {}', 'Failed to connect')
