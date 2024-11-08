"""Test module for app/legacy/v2/notifications/route_schema.py."""

from app.legacy.v2.notifications.route_schema import V2NotificationPushRequest


def test_v2_notification_push_request_valid() -> None:
    """Valid data should not raise ValidationError."""
    data = {
        'mobile_app': 'VA_FLAGSHIP_APP',
        'template_id': 'd5b6e67c-8e2a-11ee-8b8e-0242ac120002',
        'recipient_identifier': {'id_type': 'ICN', 'id_value': '12345'},
        'personalization': {'name': 'John'},
    }
    assert isinstance(V2NotificationPushRequest.model_validate(data), V2NotificationPushRequest)


# TODO: add negative tests
