"""Contains helpers for VA Profile.

- register_device_with_vaprofile: Register a device with VA Profile.
"""

from loguru import logger

from app.constants import MobileAppType


def register_device_with_vaprofile(
    endpoint_sid: str,
    device_name: str,
    device_os: str,
    app_name: MobileAppType,
    token: str,
) -> bool:
    """Register a device with VA Profile.

    Args:
        endpoint_sid (str): The endpoint SID,
        device_name (str): The device name
        device_os (str): The device OS
        app_name (str): The app name
        token (str): The token

    Returns:
        bool: True always, for now

    """
    logger.debug(
        'Registering device with VA Profile: endpoint_sid={}, device_name={}, device_os={}, app_name={}, token={}',
        endpoint_sid,
        device_name,
        device_os,
        app_name,
        token,
    )
    return True
