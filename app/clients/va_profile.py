"""Contains helpers for the VA Profile client.

- register_device_with_vaprofile: Register a device with the VA Profile.
"""

from loguru import logger


def register_device_with_vaprofile(
    endpoint_sid: str, device_name: str, device_os: str, app_name: str, token: str
) -> None:
    """Register a device with the VA Profile.

    Args:
        endpoint_sid (str): The endpoint SID,
        device_name (str): The device name
        device_os (str): The device OS
        app_name (str): The app name
        token (str): The token

    """
    logger.info(
        'Registering device with VA Profile: endpoint_sid={}, device_name={}, device_os={}, app_name={}, token={}',
        endpoint_sid,
        device_name,
        device_os,
        app_name,
        token,
    )
    return True
