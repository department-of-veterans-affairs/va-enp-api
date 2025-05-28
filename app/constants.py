"""Application Constants."""

import os
from enum import StrEnum

# AWS SQS Configuration
AWS_REGION = os.getenv('AWS_REGION_NAME', 'us-east-1')
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID', 'test')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY', 'test')

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


class QueueNames(StrEnum):
    """Celery queue names."""

    LOOKUP_CONTACT_INFO = 'lookup-contact-info-tasks'
    LOOKUP_VA_PROFILE_ID = 'lookup-va-profile-id-tasks'
    SEND_SMS = 'send-sms-tasks'
    # TODO: Remove this before merging to main
    TEST_SEND_DLQ = 'dev-bip-consumer-dead-letter-queue'
