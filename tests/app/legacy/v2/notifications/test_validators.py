"""Test module for app/legacy/v2/notifications/validators.py."""

import pytest

from app.legacy.v2.notifications.validators import validate_and_format_phone_number


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
    validated = validate_and_format_phone_number(phone_number, international=False)
    assert validated, description


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
    """Valid international phone numbers should not raise ValidationError."""
    validated = validate_and_format_phone_number(phone_number, international=True)
    assert validated, description
