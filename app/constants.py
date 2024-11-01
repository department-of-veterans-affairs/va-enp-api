"""Application Constants."""

from enum import Enum


class MobileAppType(str, Enum):
    """Mobile App Types available."""

    VETEXT = 'VETEXT'
    VA_FLAGSHIP_APP = 'VA_FLAGSHIP_APP'
