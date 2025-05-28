"""Application Constants."""

import os
from enum import StrEnum

ENV = os.getenv('ENV', 'dev')
DEPLOYMENT_ENVS = ('dev', 'perf', 'staging', 'prod')

# AWS Configuration
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')

# This should be 2886 when deployed to retry for a full 24 hours.
# Defaulting to 3 so local testing doesn't take too long.
MAX_RETRIES = int(os.getenv('MAX_RETRIES', 3))

RESPONSE_400 = 'Bad request'
RESPONSE_404 = 'Not found'
RESPONSE_500 = 'Server error'


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


class OSPlatformType(StrEnum):
    """OS Platform Types available."""

    ANDROID = 'ANDROID'
    IOS = 'IOS'


QUEUE_PREFIX = f'{ENV}-notification-'


class QueueNames(StrEnum):
    """Celery queue names."""

    LOOKUP_CONTACT_INFO = f'{QUEUE_PREFIX}lookup-contact-info-tasks'
    LOOKUP_VA_PROFILE_ID = f'{QUEUE_PREFIX}lookup-va-profile-id-tasks'
    SEND_SMS = f'{QUEUE_PREFIX}send-sms-tasks'
    # TODO: 260 - Remove this queue once notifications are persisted in the database
    TEST_SEND_DLQ = 'dev-bip-consumer-dead-letter-queue'
