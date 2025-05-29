"""Definition for ProviderAWS.

This module uses aiobotocore to make asynchronous requests to AWS.  Ideally, we would create a client once and use it
to handle all requests, but the aiobotocore docs do not explain how to create a client outside of a "with" block.
"""

import os

import botocore
from aiobotocore.session import get_session
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_full_jitter

from app.constants import MAX_RETRIES
from app.exceptions import NonRetryableError, RetryableError
from app.logging.logging_config import logger
from app.providers import sns_publish_retriable_exceptions_set
from app.providers.provider_base import ProviderBase
from app.providers.provider_schemas import DeviceRegistrationModel, PushModel, PushRegistrationModel
from app.utils import log_last_attempt_on_failure, log_on_retry


class ProviderAWS(ProviderBase):
    """Provider interface for Amazon Web Services (AWS)."""

    def __str__(self) -> str:
        """Return the name of the provider.

        Returns:
            str: The name of the provider

        """
        return 'AWS Provider'

    @staticmethod
    def get_platform_application_arn(platform_application_id: str) -> str:
        """Build the platform application ARN.

        Args:
            platform_application_id: The ID of the platform application

        Returns:
            str: The platform application ARN

        """
        region_name = os.getenv('AWS_REGION_NAME', 'us-east-1')
        account_id = os.getenv('AWS_ACCOUNT_ID', '000000000000')
        platform = os.getenv('AWS_PLATFORM', 'APNS')

        return f'arn:aws:sns:{region_name}:{account_id}:app/{platform}/{platform_application_id}'

    async def _send_push(self, push_model: PushModel) -> str:
        """Send a message to an Amazon SNS topic.

        https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/sns/client/publish.html

        Args:
            push_model: the parameters to pass to SNS.Client.publish

        Returns:
            str: A reference identifier for the sent notification

        """
        publish_params: dict[str, str | None] = {'Message': push_model.message}
        if push_model.target_arn is not None:
            publish_params['TargetArn'] = push_model.target_arn
        else:
            publish_params['TopicArn'] = push_model.topic_arn

        try:
            session = get_session()
            async with session.create_client(
                'sns',
                region_name=os.getenv('AWS_REGION_NAME', 'us-east-1'),
                aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY', ''),
                aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID', ''),
            ) as client:
                response: dict[str, str] = await client.publish(**publish_params)
        except Exception as e:
            fail_message = f'Failed to send a push notification to {push_model.target_arn or push_model.topic_arn}'
            _handle_sns_exceptions(e, fail_message)

        logger.debug(response)
        return response['MessageId']

    async def register_device(self, device_registration_model: DeviceRegistrationModel) -> str:
        """Register a mobile app user. Calls the public method register_push_endpoint, after building the arn.

        Args:
            device_registration_model: the parameters to pass to register

        Returns:
            str: The endpoint ARN needed to send a push notification to the registered device

        """
        platform_application_arn = self.get_platform_application_arn(
            device_registration_model.platform_application_name,
        )
        logger.debug('Registering device with platform application ARN {}', platform_application_arn)

        push_registration_model = PushRegistrationModel(
            platform_application_arn=platform_application_arn,
            token=device_registration_model.token,
        )
        response = await self.register_push_endpoint(push_registration_model)
        logger.debug('Registered device with endpoint ARN {}', response)

        return response

    @retry(
        before_sleep=log_on_retry,
        reraise=True,
        retry_error_callback=log_last_attempt_on_failure,
        retry=retry_if_exception_type(RetryableError),
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_full_jitter(multiplier=1, max=60),
    )
    async def register_push_endpoint(self, push_registration_model: PushRegistrationModel) -> str:
        """Register a mobile app user.

        https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/sns/client/create_platform_endpoint.html

        Args:
            push_registration_model: the parameters to pass to SNS.Client.create_platform_endpoint

        Returns:
            str: The endpoint ARN needed to send a push notification to the registered device

        """
        try:
            session = get_session()
            async with session.create_client(
                'sns',
                region_name=os.getenv('AWS_REGION_NAME', 'us-east-1'),
                aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY', ''),
                aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID', ''),
            ) as client:
                response: dict[str, str] = await client.create_platform_endpoint(
                    PlatformApplicationArn=push_registration_model.platform_application_arn,
                    Token=push_registration_model.token,
                )
        except Exception as e:
            fail_message = (
                f'Failed to register a push client with AWS SNS: {push_registration_model.platform_application_arn}'
            )
            _handle_sns_exceptions(e, fail_message)

        logger.info(
            'Created push endpoint ARN {} for device {} on application {}.',
            response['EndpointArn'],
            push_registration_model.token,
            push_registration_model.platform_application_arn,
        )
        return response['EndpointArn']


def _handle_sns_exceptions(e: Exception, fail_message: str) -> None:
    """Handle exceptions raised by SNS.

    Args:
        e (Exception): The exception that was raised
        fail_message (str): The message to log when the exception is caught

    Raises:
        RetryableError: Exception that can be retried
        NonRetryableError: Don't retry the request

    """
    if isinstance(e, botocore.exceptions.ClientError):
        if e.response.get('Error', {}).get('Code') in sns_publish_retriable_exceptions_set:
            raise RetryableError from e

    logger.exception(fail_message)
    raise NonRetryableError(fail_message) from e
