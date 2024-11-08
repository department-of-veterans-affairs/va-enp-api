"""Test module for app/legacy/v2/notifications/route_schema.py."""

from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.legacy.v2.notifications.route_schema import V2NotificationPushRequest, V2NotificationSingleRequest


def test_v2_notification_single_request() -> None:
    """Valid data should not raise ValidationError."""
    data = {'to': '12345', 'template_id': uuid4()}
    assert isinstance(V2NotificationSingleRequest.model_validate(data), V2NotificationSingleRequest)


def test_v2_notification_single_request_serialization() -> None:
    """Model can serialize data."""
    req = V2NotificationSingleRequest(to='12345', template_id=UUID('d5b6e67c-8e2a-11ee-8b8e-0242ac120002', version=4))
    serialized_data = {
        'to': '12345',
        'template_id': str(req.template_id),
        'personalisation': None,
        'reference': None,
    }

    assert req.serialize() == serialized_data


@pytest.mark.parametrize('personalisation', [None, {'name': 'John'}, {'code': 123}])
def test_v2_notification_push_request_valid(personalisation: dict[str, str | int] | None) -> None:
    """Valid data should not raise ValidationError."""
    data = {
        'mobile_app': 'VA_FLAGSHIP_APP',
        'template_id': 'd5b6e67c-8e2a-11ee-8b8e-0242ac120002',
        'recipient_identifier': {'id_type': 'ICN', 'id_value': '12345'},
        'personalisation': personalisation,
    }
    assert isinstance(V2NotificationPushRequest.model_validate(data), V2NotificationPushRequest)


@pytest.mark.parametrize(
    ('mobile_app', 'template_id', 'recipient_identifier'),
    [
        (None, 'd5b6e67c-8e2a-11ee-8b8e-0242ac120002', {'id_type': 'ICN', 'id_value': '12345'}),
        ('VA_FLAGSHIP_APP', None, {'id_type': 'ICN', 'id_value': '12345'}),
        ('VETEXT', 'd5b6e67c-8e2a-11ee-8b8e-0242ac120002', None),
    ],
    ids=['empty_mobile_app', 'empty_template_id', 'empty_recipient_identifier'],
)
def test_v2_notification_push_request_invalid(
    mobile_app: str,
    template_id: str,
    recipient_identifier: dict[str, str],
) -> None:
    """Invalid data should raise ValidationError."""
    data = {
        'mobile_app': mobile_app,
        'template_id': template_id,
        'recipient_identifier': recipient_identifier,
        'personalisation': None,
    }
    with pytest.raises(ValidationError):
        V2NotificationPushRequest.model_validate(data)
