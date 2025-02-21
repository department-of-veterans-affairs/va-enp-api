"""Test module for app/legacy/v2/notifications/validators.py."""

import pytest

from app.legacy.v2.notifications.validators import InvalidPhoneError, validate_and_format_phone_number


@pytest.mark.parametrize(
    ('phone_number', 'description'),
    [
        ('+12025550123', 'E.164 format'),
        ('+1 202 555 0123', 'US country code with spaces'),
        ('+1(202)5550123', 'US country code with parenthesis'),
        ('+1[202]5550123', 'US country code with brackets'),
        ('+1-202-555-0123', 'US country code with hyphens'),
        ('+1.202.555.0123', 'US country code with periods'),
        ('+1 (202) 555-0123', 'US country code with mixed format'),
        ('+1 (202) 555-0123x45', 'US country code with mixed format + x no spaces'),
        ('+1 (202) 555-0123 x 45', 'US country code with mixed format + x'),
        ('+1 (202) 555-0123 ext 45', 'US country code with mixed format + ext'),
        ('+1 (202) 555-0123 extension 45', 'US country code with mixed format + extension'),
        ('2025550123', 'Local 10-digit'),
        ('202 555 0123', 'Local 10-digit with spaces'),
        ('(202)5550123', 'Local 10-digit with parenthesis'),
        ('[202]5550123', 'Local 10-digit with brackets'),
        ('202-555-0123', 'Local 10-digit with hyphens'),
        ('202.555.0123', 'Local 10-digit with periods'),
        ('(202) 555-0123', 'Local 10-digit with mixed format'),
        ('(202) 555-0123x45', 'Local 10-digit with mixed format + x no spaces'),
        ('(202) 555-0123#45', 'Local 10-digit with mixed format + # no spaces'),
        ('(202) 555-0123 x 45', 'Local 10-digit with mixed format + x'),
        ('(202) 555-0123 ext 45', 'Local 10-digit with mixed format + ext'),
        ('(202) 555-0123 extension 45', 'Local 10-digit with mixed format + extension'),
        ('12025550123', 'North American dialing'),
        ('1 202 555 0123', 'North American dialing with spaces'),
        ('1(202)5550123', 'North American dialing with parenthesis'),
        ('1[202]5550123', 'North American dialing with parenthesis'),
        ('1-202-555-0123', 'North American dialing with hyphens'),
        ('1.202.555.0123', 'North American dialing with periods'),
        ('1 (202) 555-0123', 'North American dialing with mixed format'),
    ],
)
def test_validate_and_format_phone_number_local(phone_number: str, description: str) -> None:
    """Valid local phone numbers should not raise ValidationError.

    This list covers the local number formats accepted by legacy v2 validation
    """
    validated = validate_and_format_phone_number(phone_number)
    assert validated == '+12025550123', description


@pytest.mark.parametrize(
    ('phone_number', 'description'),
    [
        ('', 'Empty string (no number provided)'),
        ('09', 'Incomplete mobile prefix'),
        ('091', 'Incomplete mobile prefix'),
        ('0917123', 'Too short for a mobile number'),
        ('091712345678', 'Too long for a mobile number'),
        ('000912345678', 'Invalid mobile prefix (000)'),
        ('0917-ABC-4567', 'Contains non-numeric characters'),
        ('0917 876 543X', 'Non-numeric character in the number'),
        ('0919 000 0000', 'Unassigned mobile number prefix (000)'),
        ('0917123456', 'One digit missing in mobile number'),
        ('0917 123 45678', 'One extra digit in mobile number'),
        ('123-456-7890', 'Invalid area code'),
    ],
)
def test_validate_and_format_phone_number_invalid_local(phone_number: str, description: str) -> None:
    """Invalid local phone numbers should raise InvalidPhoneError."""
    with pytest.raises(InvalidPhoneError, match='Not a valid local number'):
        validate_and_format_phone_number(phone_number)


@pytest.mark.parametrize(
    ('phone_number', 'description'),
    [
        ('+63 917 123 4567', 'Philippines with spaces'),
        ('+63(917)1234567', 'Philippines with parentheses'),
        ('+63[917]1234567', 'Philippines with brackets'),
        ('+63-917-123-4567', 'Philippines with hyphens'),
        ('+63.917.123.4567', 'Philippines with periods'),
        ('+63 (917) 123-4567', 'Philippines with mixed format'),
    ],
)
def test_validate_and_format_phone_number_international(phone_number: str, description: str) -> None:
    """Valid international phone numbers should not raise ValidationError.

    This list covers the international number formats accepted by legacy v2 validation
    """
    validated = validate_and_format_phone_number(phone_number)
    assert validated == '+639171234567', description


@pytest.mark.parametrize(
    ('phone_number', 'description'),
    [
        ('+63', 'Missing subscriber number'),
        ('+639', 'Incomplete mobile prefix'),
        ('+6391', 'Incomplete mobile prefix'),
        ('+63-917-12345', 'Too short for a valid mobile number'),
        ('+63-917-123-456789', 'Too long for a valid mobile number'),
        ('+63-000-123-4567', 'Invalid mobile prefix (000)'),
        ('+63-901-123', 'Too short for a mobile number'),
        ('+63 917-ABC-4567', 'Contains non-numeric characters'),
        ('+63 919 876 543X', 'Non-numeric character in the number'),
    ],
)
def test_validate_and_format_phone_number_invalid_international(phone_number: str, description: str) -> None:
    """Invalid international phone numbers should raise InvalidPhoneError."""
    with pytest.raises(InvalidPhoneError, match='Not a valid number'):
        validate_and_format_phone_number(phone_number)


@pytest.mark.parametrize(
    ('phone_number', 'description'),
    [
        ('2025550123;', 'Local with semi-colon'),
        ('+63 917 123 4567;', 'Philippines with semicolon'),
    ],
)
def test_validate_and_format_phone_number_semicolon(phone_number: str, description: str) -> None:
    """Invalid phone numbers should raise InvalidPhoneError."""
    with pytest.raises(InvalidPhoneError, match='Not a valid number'):
        validate_and_format_phone_number(phone_number)
