"""Test module for app/legacy/v2/notifications/validators.py."""

import pytest

from app.constants import IdentifierType
from app.legacy.v2.notifications.validators import is_valid_recipient_id_value


@pytest.mark.parametrize(
    ('id_type', 'id_value', 'expected'),
    [
        # Valid Cases (Should Return True)
        (IdentifierType.VA_PROFILE_ID, '123', True),
        (IdentifierType.EDIPI, '1234567890', True),
        (IdentifierType.PID, '987654321', True),
        (IdentifierType.ICN, '1234567890V123456', True),
        (IdentifierType.BIRLSID, '123', True),
        # Invalid Cases (Should Return False)
        (IdentifierType.EDIPI, '1234ABC567', False),
        (IdentifierType.ICN, '1234567890123456', False),
        (IdentifierType.ICN, '123456789V123456', False),
        (IdentifierType.PID, 'PID123', False),
        (IdentifierType.BIRLSID, '', False),
        ('UNKNOWN_TYPE', '12345', False),
    ],
    ids=(
        'Recipient ID: Valid VA_PROFILE_ID with any numeric string',
        'Recipient ID: Valid EDIPI with any numeric string',
        'Recipient ID: Valid PID with any numeric string',
        'Recipient ID: Valid ICN with 10 digits + V + 6 digits',
        'Recipient ID: Valid BIRLSID weith any numeric string',
        'Recipient ID: Invalid EDIPI with non-numeric characters',
        'Recipient ID: Invalid ICN with missing V separator',
        'Recipient ID: Invalid ICN with missing digit in prefix',
        'Recipient ID: Invalid PID with non-numeric charaters',
        'Recipient ID: Invalid BIRLSID with empty string',
        'Recipient ID Type: Invalid recipient id type',
    ),
)
def test_is_valid_recipient_id_value(id_type: IdentifierType, id_value: str, expected: bool) -> None:
    """Test is_valid_recipient_id_value with multiple valid and invalid cases."""
    if expected:
        assert is_valid_recipient_id_value(id_type, id_value)
    else:
        assert not is_valid_recipient_id_value(id_type, id_value)
