"""Tests for DAO utils methods."""

from typing import Union

import pytest

from app.legacy.dao.utils import Serializer

PayloadType = Union[
    str,
    int,
    float,
    bool,
    dict[str, str],
    list[str],
    None,
]


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
def test_serialize_deserialize_round_trip(payload: PayloadType) -> None:
    """Test that serializer can perform a round-trip serialize/deserialize."""
    serializer = Serializer()

    encoded = serializer.serialize(payload)
    decoded = serializer.deserialize(encoded)
    assert decoded == payload
