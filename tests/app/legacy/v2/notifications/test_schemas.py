"""Test module for app/legacy/v2/notifications/route_schema.py.

The tests cover Pydantic models that have custom validation.
"""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.constants import IdentifierType
from app.legacy.v2.notifications.route_schema import (
    V2PostEmailRequestModel,
    V2PostSmsRequestModel,
)

VALID_PHONE_NUMBER = '+17045555555x5'
INVALID_PHONE_NUMBER = '+5555555555'
VALID_ICN_VALUE = '1234567890V123456'

######################################################################
# Test POST e-mail schemas
######################################################################


@pytest.mark.parametrize(
    'data',
    [
        {'email_address': 'test@va.gov'},
        {'recipient_identifier': {'id_type': IdentifierType.ICN, 'id_value': VALID_ICN_VALUE}},
    ],
    ids=(
        'e-mail address',
        'recipient ID',
    ),
)
def test_v2_post_email_request_model_valid(data: dict[str, str | dict[str, str]]) -> None:
    """Valid data with an e-mail address should not raise ValidationError."""
    data['email_reply_to_id'] = str(uuid4())
    data['template_id'] = str(uuid4())
    assert isinstance(V2PostEmailRequestModel.model_validate(data), V2PostEmailRequestModel)


@pytest.mark.parametrize(
    'data',
    [
        {},
        {'email_address': 'test@va.gov', 'recipient_identifier': {'id_type': 'ICN', 'id_value': 'test'}},
    ],
    ids=(
        'neither e-mail address nor recipient ID',
        'e-mail address and recipient ID',
    ),
)
def test_v2_post_email_request_model_invalid(data: dict[str, str | dict[str, str]]) -> None:
    """Invalid data should raise ValidationError."""
    data['email_reply_to_id'] = str(uuid4())
    data['template_id'] = str(uuid4())

    with pytest.raises(ValidationError):
        V2PostEmailRequestModel.model_validate(data)


######################################################################
# Test POST SMS schemas
######################################################################


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
def test_v2_post_sms_request_model_valid_local(phone_number: str, description: str) -> None:
    """Valid required data should not raise ValidationError."""
    data = dict()
    data['phone_number'] = phone_number
    data['template_id'] = str(uuid4())

    request = V2PostSmsRequestModel.model_validate(data)
    assert isinstance(request, V2PostSmsRequestModel), description

    if request.phone_number is not None:
        assert request.phone_number == '+12025550123'


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
def test_v2_post_sms_request_model_valid_international(phone_number: str, description: str) -> None:
    """Valid required data should not raise ValidationError."""
    data = dict()
    data['phone_number'] = phone_number
    data['template_id'] = str(uuid4())

    request = V2PostSmsRequestModel.model_validate(data)
    assert isinstance(request, V2PostSmsRequestModel), description

    if request.phone_number is not None:
        assert request.phone_number == '+639171234567'


@pytest.mark.parametrize(
    ('phone_number', 'description'),
    [
        ('', 'Empty string (no number provided)'),
        (1234, 'Non-string'),
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
        ('+63', 'Missing subscriber number'),
        ('+639', 'Incomplete mobile prefix'),
        ('+6391', 'Incomplete mobile prefix'),
        ('+63-917-12345', 'Too short for a valid mobile number'),
        ('+63-917-123-456789', 'Too long for a valid mobile number'),
        ('+63-000-123-4567', 'Invalid mobile prefix (000)'),
        ('+63-901-123', 'Too short for a mobile number'),
        ('+63 919 876 543X', 'Non-numeric character in the number'),
    ],
)
def test_v2_post_sms_request_model_invalid_phone(phone_number: str | int, description: str) -> None:
    """Invalid phone numbers should raise ValidationError."""
    data = dict()
    data['phone_number'] = phone_number
    data['template_id'] = str(uuid4())

    with pytest.raises(ValidationError):
        V2PostSmsRequestModel.model_validate(data)


@pytest.mark.parametrize(
    'data',
    [
        {'phone_number': VALID_PHONE_NUMBER},
        {'recipient_identifier': {'id_type': IdentifierType.ICN, 'id_value': VALID_ICN_VALUE}},
        {
            'phone_number': VALID_PHONE_NUMBER,
            'recipient_identifier': {'id_type': IdentifierType.ICN, 'id_value': VALID_ICN_VALUE},
        },
    ],
    ids=(
        'phone number',
        'recipient ID',
        'phone number and recipient ID',
    ),
)
def test_v2_post_sms_request_model_valid(data: dict[str, str | dict[str, str]]) -> None:
    """Valid required data should not raise ValidationError."""
    data['sms_sender_id'] = str(uuid4())
    data['template_id'] = str(uuid4())

    request = V2PostSmsRequestModel.model_validate(data)
    assert isinstance(request, V2PostSmsRequestModel)

    if request.phone_number is not None:
        assert request.phone_number == '+17045555555'


@pytest.mark.parametrize(
    'data',
    [
        {},
        {'phone_number': INVALID_PHONE_NUMBER},
    ],
    ids=(
        'neither phone number nor recipient ID',
        'invalid us phone number',
    ),
)
def test_v2_post_sms_request_model_invalid(data: dict[str, str | dict[str, str]]) -> None:
    """Invalid data should raise ValidationError."""
    data['sms_sender_id'] = str(uuid4())
    data['template_id'] = str(uuid4())
    with pytest.raises(ValidationError):
        V2PostSmsRequestModel.model_validate(data)
