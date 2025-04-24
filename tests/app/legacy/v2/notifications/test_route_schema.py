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

VALID_PHONE_NUMBER = '2025550123'
VALID_PHONE_NUMBER_E164 = '+12025550123'
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
    data['template_id'] = str(uuid4())

    with pytest.raises(ValidationError):
        V2PostEmailRequestModel.model_validate(data)


######################################################################
# Test POST SMS schemas
######################################################################


@pytest.mark.parametrize(
    ('phone_number', 'description'),
    [
        ('1800INVALID', 'Local non-numeric number'),
        ('+63919INVALID', 'International non-numeric number'),
    ],
)
def test_v2_post_sms_request_model_invalid_phone_number(phone_number: str | int, description: str) -> None:
    """Invalid non-numeric vanity phone numbers should raise ValidationError."""
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
    ],
    ids=(
        'phone number',
        'recipient ID',
    ),
)
def test_v2_post_sms_request_model_valid(data: dict[str, str | dict[str, str]]) -> None:
    """Valid required data should not raise ValidationError."""
    data['sms_sender_id'] = str(uuid4())
    data['template_id'] = str(uuid4())

    request = V2PostSmsRequestModel.model_validate(data)
    assert isinstance(request, V2PostSmsRequestModel)

    if request.phone_number is not None:
        assert request.phone_number == VALID_PHONE_NUMBER_E164


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
