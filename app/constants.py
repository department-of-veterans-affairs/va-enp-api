"""Application Constants."""

from enum import StrEnum


class IdentifierType(StrEnum):
    """Types of Identifiers that can be used."""

    VA_PROFILE_ID = 'VAPROFILEID'
    PID = 'PID'
    ICN = 'ICN'
    BIRLSID = 'BIRLSID'
    EDIPI = 'EDIPI'

    @staticmethod
    def values() -> list[str]:
        """Get the values of the Enum.

        Returns:
            list[str]: The values of the Enum

        """
        return list(x.value for x in IdentifierType)


# made specific enum for ICN so api spec is clear
class IdentifierTypeICN(StrEnum):
    """Specific Enum type for ICN."""

    ICN = IdentifierType.ICN.value


class MobileAppType(StrEnum):
    """Mobile App Types available."""

    VETEXT = 'VETEXT'
    VA_FLAGSHIP_APP = 'VA_FLAGSHIP_APP'
