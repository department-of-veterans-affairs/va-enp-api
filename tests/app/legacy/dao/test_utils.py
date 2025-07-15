"""Tests for DAO utils methods."""

import pytest

from app.legacy.dao.utils import Serializer


@pytest.mark.parametrize(
    'payload',
    [
        'hello',
        123,
        3.14,
        True,
        None,
        {'foo': 'bar'},
        ['a', 'b', 'c'],
    ],
)
def test_serialize_deserialize_round_trip(payload: object | str | dict[str, str] | int | float | bool | None) -> None:
    """Test that serializer can perform a round-trip serialize/deserialize."""
    serializer = Serializer()

    encoded = serializer.serialize(payload)
    decoded = serializer.deserialize(encoded)
    assert decoded == payload
