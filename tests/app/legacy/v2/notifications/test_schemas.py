"""Test module for app/legacy/v2/notifications/route_schema.py.

The tests cover Pydantic models that have custom validation.
"""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.constants import IdentifierType
from app.legacy.v2.notifications.route_schema import (
    RecipientIdentifierModel,
    V2PostEmailRequestModel,
    V2PostNotificationRequestModel,
    V2PostSmsRequestModel,
)


@pytest.mark.parametrize('data', ({'id_type': id_type} for id_type in IdentifierType))
def test_recipient_identifier_model_id_type_valid(data: dict[str, str | dict[str, str]]) -> None:
    """Recipient identifier with valid id_type should not raise ValidationError."""
    data['id_value'] = 'foo'

    # model validates
    assert isinstance(RecipientIdentifierModel.model_validate(data), RecipientIdentifierModel)


@pytest.mark.parametrize(
    'data',
    [
        {'id_type': ''},
        {'id_type': 'foo'},
        {'id_type': None},
    ],
)
def test_recipient_identifier_model_id_type_invalid(data: dict[str, str | dict[str, str]]) -> None:
    """Recipient identifier with invalid id_type should raise ValidationError."""
    data = {'id_value': 'bar'}

    with pytest.raises(ValidationError):
        RecipientIdentifierModel.model_validate(data)


@pytest.mark.parametrize(
    'data',
    [
        {'personalisation': {'field': 'value'}},
        {'personalization': {'field': 'value'}},
    ],
)
def test_v2_post_notification_request_model_personalisation_alias_valid(data: dict[str, str | dict[str, str]]) -> None:
    """Valid required data with either spelling of personalisation should not raise ValidationError.

    Test fields common to models extending on V2PostNotificationRequestModel
    """
    data['template_id'] = str(uuid4())
    model: V2PostNotificationRequestModel = V2PostNotificationRequestModel.model_validate(data)

    # model validates
    assert isinstance(model, V2PostNotificationRequestModel)

    # personalisation present and populated
    assert model.personalisation.get('field') == 'value' if model.personalisation else None

    # personalization alias not present
    assert not hasattr(model, 'personalization')


@pytest.mark.parametrize(
    'url',
    [
        None,
        'https://example.com',
        'https://sub.example.com',
        'https://example.com:8080',
        'https://example.com/path/to/resource',
        'https://example.com/search?q=foo',
        'https://192.168.1.1',
        'https://user:password@example.com',
    ],
)
def test_v2_post_notification_request_model_callback_url_valid(url: str) -> None:
    """Valid required data with valid callback url should not raise ValidationError.

    Test fields common to models extending on V2PostNotificationRequestModel
    """
    data = {
        'callback_url': url,
        'template_id': str(uuid4()),
    }
    assert isinstance(V2PostNotificationRequestModel.model_validate(data), V2PostNotificationRequestModel)


@pytest.mark.parametrize(
    'url',
    ['example.com', 'ftp://example.com', 'http://example.com'],
)
def test_v2_post_notification_request_model_callback_url_invalid(url: str) -> None:
    """Valid required data with invalid callback url should raise ValidationError.

    Test fields common to models extending on V2PostNotificationRequestModel
    """
    data = {
        'callback_url': url,
        'template_id': str(uuid4()),
    }
    with pytest.raises(ValidationError):
        V2PostNotificationRequestModel.model_validate(data)


######################################################################
# Test POST e-mail schemas
######################################################################


@pytest.mark.parametrize(
    'data',
    [
        {'email_address': 'test@va.gov'},
        {'recipient_identifier': {'id_type': 'ICN', 'id_value': 'test'}},
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


valid_phone_number = '+17045555555'
invalid_phone_number = '+5555555555'


@pytest.mark.parametrize(
    'data',
    [
        {'phone_number': valid_phone_number},
        {'recipient_identifier': {'id_type': 'ICN', 'id_value': 'test'}},
        {'phone_number': valid_phone_number, 'recipient_identifier': {'id_type': 'ICN', 'id_value': 'test'}},
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
    assert isinstance(V2PostSmsRequestModel.model_validate(data), V2PostSmsRequestModel)


@pytest.mark.parametrize(
    'data',
    [
        {},
        {'phone_number': invalid_phone_number},
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
