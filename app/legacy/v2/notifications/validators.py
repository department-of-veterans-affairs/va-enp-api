"""Validation functions."""

import re

from app.constants import IdentifierType


def is_valid_recipient_id_value(id_type: IdentifierType, id_value: str) -> bool:
    """Validates id_value based on the corresponding id_type.

    Args:
        id_type (IdentifierType): What type of identifier pattern to validate against
        id_value (str): The id string to validate

    Returns:
        bool: Is the id_value valid for the specified type

    """
    id_patterns = {
        IdentifierType.VA_PROFILE_ID: r'^\d+$',  # Any numeric string
        IdentifierType.EDIPI: r'^\d+$',  # Any numeric string
        IdentifierType.PID: r'^\d+$',  # Any numeric string
        IdentifierType.ICN: r'^\d{10}V\d{6}$',  # 10 digits + 'V' + 6 digits
        IdentifierType.BIRLSID: r'^\d+$',  # Any numeric string
    }

    # Validate ID format if a pattern exists for the given id_type
    if id_type in id_patterns:
        is_valid = bool(re.match(id_patterns[id_type], id_value))
    else:
        is_valid = False

    return is_valid
