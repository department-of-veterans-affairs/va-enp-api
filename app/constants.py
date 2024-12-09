"""Application Constants."""

from enum import StrEnum

from phonenumbers import PhoneNumberFormat
from pydantic_extra_types.phone_numbers import PhoneNumber

# this should be 2886 to retry for a full 24 hours
# setting to 3 for now so local testing doesn't take too long
MAX_RETRIES = 3

RESPONSE_400 = 'Bad request'
RESPONSE_404 = 'Not found'
RESPONSE_500 = 'Server error'


class IdentifierType(StrEnum):
    """Types of Identifiers that can be used."""

    BIRLSID = 'BIRLSID'
    EDIPI = 'EDIPI'
    ICN = 'ICN'
    PID = 'PID'
    VA_PROFILE_ID = 'VAPROFILEID'


class MobileAppType(StrEnum):
    """Mobile App Types available."""

    VA_FLAGSHIP_APP = 'VA_FLAGSHIP_APP'
    VETEXT = 'VETEXT'


class NotificationType(StrEnum):
    """Types of Notifications that can be sent."""

    EMAIL = 'email'
    PUSH = 'push'
    SMS = 'sms'


class OSPlatformType(StrEnum):
    """OS Platform Types available."""

    ANDROID = 'ANDROID'
    IOS = 'IOS'


class USNumberType(PhoneNumber):
    """Annotated type for US phone numbers."""

    supported_regions = ['US']  # noqa: RUF012
    phone_format: str = PhoneNumberFormat.to_string(PhoneNumberFormat.E164)
