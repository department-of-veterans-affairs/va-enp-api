from loguru import logger


def register_device_with_vaprofile(endpoint_sid: str, device_name: str, device_os: str):
    """Register a device with the VA Profile.

    Args:
        endpoint_sid (str): The endpoint SID
        device_name (str): The device name
        device_os (str): The device OS

    """
    logger.info(
        'Registering device with VA Profile: endpoint_sid={}, device_name={}, device_os={}',
        endpoint_sid,
        device_name,
        device_os,
    )

    return True
