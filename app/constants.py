"""Application Constants."""

import os
from enum import StrEnum

ENV = os.getenv('ENV', 'local')
DEPLOYMENT_ENVS = ('dev', 'perf', 'staging', 'prod')

# AWS Configuration
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')

# This should be 2886 when deployed to retry for a full 24 hours.
# Defaulting to 3 so local testing doesn't take too long.
MAX_RETRIES = int(os.getenv('MAX_RETRIES', 3))

# Time calculations
FIVE_MINUTES = 5 * 60
TWELVE_HOURS = 12 * 60 * 60


class AttachmentType(StrEnum):
    """Types of file attachment methods that can be used."""

    ATTACH = 'attach'
    LINK = 'link'


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


class NotificationStatus(StrEnum):
    """Types of Notifications that can be sent."""

    CREATED = 'created'


class OSPlatformType(StrEnum):
    """OS Platform Types available."""

    ANDROID = 'ANDROID'
    IOS = 'IOS'


QUEUE_PREFIX = f'{ENV}-notification-'


class QueueNames(StrEnum):
    """Celery queue names."""

    LOOKUP_CONTACT_INFO = 'lookup-contact-info-tasks'
    LOOKUP_VA_PROFILE_ID = 'lookup-va-profile-id-tasks'
    SEND_SMS = 'send-sms-tasks'


# Legacy auth responses
RESPONSE_LEGACY_INVALID_TOKEN_WRONG_TYPE = 'Invalid token: service id is not the right data type'  # nosec
RESPONSE_LEGACY_INVALID_TOKEN_NO_SERVICE = 'Invalid token: service not found'  # nosec
RESPONSE_LEGACY_INVALID_TOKEN_ARCHIVED_SERVICE = 'Invalid token: service is archived'  # nosec
RESPONSE_LEGACY_INVALID_TOKEN_NOT_FOUND = 'Invalid token: signature, api token not found'  # nosec
RESPONSE_LEGACY_INVALID_TOKEN_NOT_VALID = 'Invalid token: signature, api token is not valid'  # nosec
RESPONSE_LEGACY_INVALID_TOKEN_NO_ISS = 'Invalid token: iss field not provided'  # nosec
RESPONSE_LEGACY_INVALID_TOKEN_NO_KEYS = 'Invalid token: service has no API keys'  # nosec
RESPONSE_LEGACY_INVALID_TOKEN_REVOKED = 'Invalid token: API key revoked'  # nosec
RESPONSE_LEGACY_ERROR_SYSTEM_CLOCK = 'Error: Your system clock must be accurate to within 30 seconds'
RESPONSE_LEGACY_NO_CREDENTIALS = 'Unauthorized, authentication token must be provided'

# ENP responses
RESPONSE_400 = 'Bad request'
RESPONSE_403 = 'Not authenticated'
RESPONSE_404 = 'Not found'
RESPONSE_429 = 'Rate limit exceeded'
RESPONSE_500 = 'Server error'
