"""Contains helpers for VA Profile.

- register_device_with_vaprofile: Register a device with VA Profile.
- get_contact_info: Get contact information for a user from VA Profile.
"""

import asyncio
from typing import Dict

from loguru import logger

from app.constants import MobileAppType, OSPlatformType


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


async def get_contact_info(id_type: str, id_value: str) -> Dict[str, str]:
    """Get contact information for a user from VA Profile.

    Args:
        id_type (str): Type of identifier (e.g., ICN)
        id_value (str): Identifier value

    Returns:
        Dict[str, str]: Dictionary containing contact information (email, phone_number)

    Raises:
        ConnectionError: If there's an error connecting to VA Profile
        ValueError: If the provided identifier is invalid
        KeyError: If the user is not found
    """
    logger.debug('Getting contact info from VA Profile for identifier type {} and value {}', id_type, id_value)

    # Validate the input
    if not id_value or len(id_value) < 8:
        logger.error('Invalid identifier value provided: too short')
        raise ValueError(f"Invalid identifier value format for type '{id_type}'")

    try:
        # This is a placeholder implementation
        # In a real implementation, this would make an API call to VA Profile service
        # Simulate a network request with a small delay
        await asyncio.sleep(0.1)

        # In a real implementation, we would check if the user exists
        if id_value.endswith('0000'):
            raise KeyError(f'User with {id_type} not found')

        masked_id = f'{id_value[:-6]}XXXXXX' if len(id_value) > 6 else 'XXXXXX'
        logger.info('Successfully retrieved contact information for {}', masked_id)

        # In a real implementation, this would be the actual data from VA Profile
        contact_info = {
            'email': f'user-{id_value[-6:]}@example.com',
            'phone_number': f'+18005551{id_value[-3:]}',
        }
    except ConnectionError as e:
        logger.error('Connection to VA Profile failed: {}', str(e))
        raise
    except Exception as e:
        logger.exception('Unexpected error in VA Profile connection: {}', str(e))
        raise ConnectionError(f'Error retrieving data from VA Profile: {e}')

    return contact_info
