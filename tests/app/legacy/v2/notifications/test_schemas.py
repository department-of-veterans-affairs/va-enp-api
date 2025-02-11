"""Test module for app/legacy/v2/notifications/route_schema.py.

The tests cover Pydantic models that have custom validation.
"""

from uuid import UUID, uuid1, uuid4

import pytest
from pydantic import ValidationError

from app.constants import AttachmentSendingMethodType, IdentifierType
from app.legacy.v2.notifications.route_schema import (
    RecipientIdentifierModel,
    V2PostEmailRequestModel,
    V2PostNotificationRequestModel,
    V2PostSmsRequestModel,
    parse_uuid4,
    uuid4_before_validator,
)


@pytest.mark.parametrize(
    'value',
    [None, uuid4(), str(uuid4())],
)
def test_uuid4_before_validator_valid_data(value: str | UUID | None) -> None:
    """Valid data should retrun a UUID object."""
    result = uuid4_before_validator(value)

    if value is None:
        assert result is None
    else:
        assert isinstance(result, UUID)


@pytest.mark.parametrize(
    ('value', 'error_msg'),
    [
        ('', 'Expected a valid UUID4'),
        ('foo', 'Expected a valid UUID4'),
        (1, 'Expected a valid UUID4'),
        (uuid1(), 'UUID must be version 4'),
    ],
)
def test_uuid4_before_validator_invalid_data(value: str | int | UUID, error_msg: str) -> None:
    """Invalid data should throw ValueError exception."""
    with pytest.raises(ValueError, match=error_msg):
        uuid4_before_validator(value)


def test_parse_uuid4_valid_data() -> None:
    """Valid data should retrun a UUID object."""
    assert isinstance(parse_uuid4(str(uuid4())), UUID)


@pytest.mark.parametrize(
    ('value', 'error_msg'),
    [
        ('', 'Expected a valid UUID4'),
        ('foo', 'Expected a valid UUID4'),
        ('1', 'Expected a valid UUID4'),
        (str(uuid1()), 'UUID must be version 4'),
    ],
)
def test_parse_uuid4_invalid_data(value: str, error_msg: str) -> None:
    """Invalid data should throw ValueError exception."""
    with pytest.raises(ValueError, match=error_msg):
        parse_uuid4(value)


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
        {'personalisation': {'field': 100}},
        {'personalisation': {'field': 100.1}},
        {'personalisation': {'field1': 'value1', 'field2': 'value2'}},
        {'personalisation': {'field': ['value1', 'value2']}},
        {'personalisation': {'field1': ['value1', 'value2'], 'field2': 'value2'}},
        {'personalisation': {'field': {'file': 'U29tZSByYW5kb20gZmlsZSBkYXRh', 'filename': 'filename'}}},
        {
            'personalisation': {
                'field': {
                    'file': 'U29tZSByYW5kb20gZmlsZSBkYXRh',
                    'filename': 'filename',
                    'sending_method': AttachmentSendingMethodType.ATTACH,
                }
            }
        },
    ],
)
def test_v2_post_notification_request_model_personalisation_valid_data(
    data: dict[str, str | int | float | list[str | int | float] | dict[str, str]],
) -> None:
    """Valid required data with either spelling of personalisation should not raise ValidationError.

    Test fields common to models extending on V2PostNotificationRequestModel
    """
    data['template_id'] = str(uuid4())

    # model validates
    assert isinstance(V2PostNotificationRequestModel.model_validate(data), V2PostNotificationRequestModel)


@pytest.mark.parametrize(
    'data',
    [
        {'personalisation': {'field': {'file': 'U29tZSByYW5kb20gZmlsZSBkYXRh'}}},
        {'personalisation': {'field': {'filename': 'filename'}}},
        {
            'personalisation': {
                'field': {'file': 'U29tZSByYW5kb20gZmlsZSBkYXRh', 'filename': 'filename', 'sending_method': 'foo'}
            }
        },
    ],
)
def test_v2_post_notification_request_model_personalisation_invalid_data(
    data: dict[str, str | list[str] | dict[str, str]],
) -> None:
    """Valid required data with either spelling of personalisation should not raise ValidationError.

    Test fields common to models extending on V2PostNotificationRequestModel
    """
    data['template_id'] = str(uuid4())

    with pytest.raises(ValidationError):
        V2PostNotificationRequestModel.model_validate(data)


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
        {'recipient_identifier': {'id_type': IdentifierType.ICN, 'id_value': 'test'}},
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
        {'recipient_identifier': {'id_type': IdentifierType.ICN, 'id_value': 'test'}},
        {
            'phone_number': valid_phone_number,
            'recipient_identifier': {'id_type': IdentifierType.ICN, 'id_value': 'test'},
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
