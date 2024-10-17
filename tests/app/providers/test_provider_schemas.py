"""Test module for app/providers/provider_schemas.py."""

import pytest
from pydantic import ValidationError

from app.providers.provider_schemas import PushModel


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
