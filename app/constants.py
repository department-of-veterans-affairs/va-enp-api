"""Application Constants."""

from enum import StrEnum

RESPONSE_400 = 'Request body failed validation'
RESPONSE_404 = 'Not found'
RESPONSE_500 = 'Unhandled VA Notify exception'


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
