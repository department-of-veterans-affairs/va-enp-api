"""Test module for app/providers/provider_schemas.py."""

import pytest
from pydantic import ValidationError

from app.providers.provider_schemas import PushModel, PushRegistrationModel


@pytest.mark.parametrize(
    'data',
    [
        {'message': 'This is a message.', 'target_arn': 'This is an ARN.'},
        {'message': 'This is a message.', 'topic_arn': 'This is an ARN.'},
    ],
    ids=(
        'target',
        'topic',
    ),
)
def test_PushModel_valid(data: dict[str, str]) -> None:
    """Valid data should not raise ValidationError."""
    assert isinstance(PushModel.model_validate(data), PushModel)


@pytest.mark.parametrize(
    'data',
    [
        {'message': 'This is a message.'},
        {'message': 'This is a message.', 'target_arn': 'This is an ARN.', 'topic_arn': 'This is an ARN.'},
    ],
    ids=(
        'no ARN',
        'multiple ARNs',
    ),
)
def test_PushModel_invalid(data: dict[str, str]) -> None:
    """Invalid data should raise ValidationError."""
    with pytest.raises(ValidationError):
        PushModel.model_validate(data)


@pytest.mark.parametrize(
    ('data', 'is_valid'),
    [
        ({'platform_application_arn': 'arn', 'token': 'token'}, True),
        ({'platform_application_arn': 'arn'}, False),
        ({'token': 'token'}, False),
        ({}, False),
    ],
    ids=(
        'valid',
        'no token',
        'no ARN',
        'empty data',
    ),
)
def test_PushRegistrationModel_valid(data: dict[str, str], is_valid: bool) -> None:
    """Test the PushRegistrationModel schema."""
    if is_valid:
        assert isinstance(PushRegistrationModel.model_validate(data), PushRegistrationModel)
    else:
        with pytest.raises(ValidationError):
            PushRegistrationModel.model_validate(data)
