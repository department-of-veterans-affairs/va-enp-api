"""Application Constants."""

from enum import StrEnum

EMAIL_TYPE = 'email'
PUSH_TYPE = 'push'
SMS_TYPE = 'sms'
NOTIFICATION_TYPE = (EMAIL_TYPE, PUSH_TYPE, SMS_TYPE)

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


# made specific enum for ICN so api spec is clear
class IdentifierTypeICN(StrEnum):
    """Specific Enum type for ICN."""

    ICN = IdentifierType.ICN.value


class MobileAppType(StrEnum):
    """Mobile App Types available."""

    VA_FLAGSHIP_APP = 'VA_FLAGSHIP_APP'
    VETEXT = 'VETEXT'


class OSPlatformType(StrEnum):
    """OS Platform Types available."""

    ANDROID = 'ANDROID'
    IOS = 'IOS'
