"""Test module for app/legacy/v2/notifications/validators.py."""

import pytest

from app.constants import IdentifierType
from app.legacy.v2.notifications.validators import is_valid_recipient_id_value


@pytest.mark.parametrize(
    ('id_type', 'id_value', 'expected'),
    [
        # Valid Cases (Should Return True)
        (IdentifierType.VA_PROFILE_ID, '123', True),  # Any numeric string
        (IdentifierType.EDIPI, '1234567890', True),  # Any numeric string
        (IdentifierType.PID, '987654321', True),  # Any numeric string
        (IdentifierType.ICN, '1234567890V123456', True),  # 10 digits + 'V' + 6 digits
        (IdentifierType.BIRLSID, '123', True),  # Any numeric string
        # Invalid Cases (Should Return False)
        (IdentifierType.EDIPI, '1234ABC567', False),  # Non-numeric EDIPI
        (IdentifierType.ICN, '1234567890123456', False),  # Missing 'V' separator
        (IdentifierType.ICN, '123456789V123456', False),  # Missing a digit before 'V'
        (IdentifierType.PID, 'PID123', False),  # Non-numeric PID
        (IdentifierType.BIRLSID, '', False),  # Empty string should fail
        ('UNKNOWN_TYPE', '12345', False),  # Unknown id_type should return False
    ],
)
def test_is_valid_recipient_id_value(id_type: IdentifierType, id_value: str, expected: bool) -> None:
    """Test is_valid_recipient_id_value with multiple valid and invalid cases."""
    assert is_valid_recipient_id_value(id_type, id_value) == expected
