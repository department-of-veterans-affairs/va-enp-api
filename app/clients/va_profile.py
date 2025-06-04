"""Contains helpers for VA Profile.

- register_device_with_vaprofile: Register a device with VA Profile.
"""

from app.constants import MobileAppType, OSPlatformType
from app.logging.logging_config import logger


def register_device_with_vaprofile(
    endpoint_sid: str,
    device_name: str,
    device_os: OSPlatformType,
    app_name: MobileAppType,
    token: str,
) -> bool:
    """Register a device with VA Profile.

    Args:
        endpoint_sid (str): The endpoint SID,
        device_name (str): The device name
        device_os (OSPlatformType): The device OS
        app_name (MobileAppType): The app name
        token (str): The token

    Returns:
        bool: True always, for now

    """
    logger.info('Registering device with VA Profile: endpoint_sid={}, app_name={}', endpoint_sid, app_name)
    logger.debug(
        'Registering device with VA Profile: endpoint_sid={}, device_name={}, device_os={}, app_name={}',
        endpoint_sid,
        device_name,
        device_os,
        app_name,
    )
    return True
