"""Validation functions."""

import os
import re

import phonenumbers

from app.constants import IdentifierType

PHONE_COUNTRY_CODE = int(os.getenv('PHONE_COUNTRY_CODE', '1'))
PHONE_REGION_CODE = os.getenv('PHONE_REGION_CODE', 'US')


class InvalidPhoneError(Exception):
    """Exception raised for invalid phone numbers.

    Attributes:
        message (str): Explanation of the error.
    """

    def __init__(self, message: str) -> None:
        """Initialize the exception with a message.

        Args:
            message (str): The error message describing the invalid phone number.
        """
        super().__init__(message)
        self.message = message


def validate_and_format_phone_number_pydantic(phone_number: str, international: bool = False) -> str:
    """Wrapper to catch InvalidPhoneError and re-raise as ValueError to work as Pydantic validator.

    Args:
        phone_number (str): A string containing a phone number
        international (bool): Look for an international number

    Returns:
        str: A valid phone number in E.164 format

    Raises:
        ValueError: Unable to parse or number is invalid
    """
    try:
        return validate_and_format_phone_number(phone_number, international)
    except InvalidPhoneError as e:
        # Pydantic will catch and format a ValueError
        raise ValueError(e.message)


def validate_and_format_phone_number(phone_number: str, international: bool = False) -> str:
    """Validate a phone number string and return its E.164 formatted version if valid.

    Args:
        phone_number (str): A string containing a phone number
        international (bool): Look for an international number

    Returns:
        str: A valid phone number in E.164 format

    Raises:
        InvalidPhoneError: Unable to parse or number is invalid
    """
    if ';' in phone_number:
        raise InvalidPhoneError('Not a valid number')

    # Determine parsing region
    if international or phone_number.startswith('+'):
        # international or looks like it has country code
        region = None
    else:
        region = PHONE_REGION_CODE

    parsed_number = parse_phone_number(phone_number, region)

    # Format to E.164
    e164_number = phonenumbers.format_number(parsed_number, phonenumbers.PhoneNumberFormat.E164)

    return e164_number


def parse_phone_number(phone_number: str, region: str | None = None) -> phonenumbers.PhoneNumber:
    """Parse and return the first phone number from a string.

    Args:
        phone_number (str): A string containing a phone number
        region (str): Two-letter ISO 3166-1 alpha-2 country code

    Returns:
        phonenumbers.PhoneNumber

    Raises:
        InvalidPhoneError: Unable to parse number
    """
    # parse the input string for phone numbers
    match_iter = iter(phonenumbers.PhoneNumberMatcher(phone_number, region))

    match = next(match_iter, None)

    if match is None:
        if region is None:
            raise InvalidPhoneError('Not a valid number')
        else:
            raise InvalidPhoneError('Not a valid local number')

    return match.number


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
        pattern = id_patterns[id_type]
        is_valid = bool(re.match(pattern, id_value))
    else:
        is_valid = False

    return is_valid
