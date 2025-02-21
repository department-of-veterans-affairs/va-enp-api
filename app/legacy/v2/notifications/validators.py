"""Validation functions."""

import os

import phonenumbers

PHONE_COUNTRY_CODE = int(os.getenv('PHONE_COUNTRY_CODE', '1'))
PHONE_REGION_CODE = os.getenv('PHONE_REGION_CODE', 'US')


class InvalidPhoneError(Exception):
    """Invalid phone number."""

    pass


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

    # Check if the number is valid
    if not phonenumbers.is_valid_number(parsed_number):
        raise InvalidPhoneError('Not a valid number')

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
