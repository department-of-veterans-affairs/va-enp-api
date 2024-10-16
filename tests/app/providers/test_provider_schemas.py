"""Test module for app/providers/provider_schemas.py."""

import pytest
from pydantic import ValidationError

from app.providers.provider_schemas import PushModel


@pytest.mark.parametrize(
    'data',
    [
        {'Message': 'This is a message.', 'TargetArn': 'This is an ARN.'},
        {'Message': 'This is a message.', 'TopicArn': 'This is an ARN.'},
    ],
    ids=(
        'target',
        'topic',
    ),
)
def test_PushModel_valid(data: dict) -> None:
    """Valid data should not raise ValidationError."""
    assert isinstance(PushModel.model_validate(data), PushModel)


@pytest.mark.parametrize(
    'data',
    [
        {'Message': 'This is a message.'},
        {'Message': 'This is a message.', 'TargetArn': 'This is an ARN.', 'TopicArn': 'This is an ARN.'},
    ],
    ids=(
        'no ARN',
        'multiple ARNs',
    ),
)
def test_PushModel_invalid(data: dict) -> None:
    """Invalid data should raise ValidationError."""
    with pytest.raises(ValidationError):
        PushModel.model_validate(data)
