"""Definition for ProviderAWS.

This module uses aiobotocore to make asynchronous requests to AWS.  Ideally, we would create a client once and use it
to handle all requests, but the aiobotocore docs do not explain how to create a client outside of a "with" block.
"""

import os

import botocore
from aiobotocore.session import get_session
from loguru import logger

from app.providers import sns_publish_retriable_exceptions_set
from app.providers.provider_base import ProviderBase, ProviderNonRetryableError, ProviderRetryableError
from app.providers.provider_schemas import PushModel, PushRegistrationModel


class ProviderAWS(ProviderBase):
    """Provider interface for Amazon Web Services (AWS)."""

    async def _send_push(self, push_model: PushModel) -> str:
        """Send a message to an Amazon SNS topic.

        https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/sns/client/publish.html

        Args:
        ----
            push_model: the parameters to pass to SNS.Client.publish

        Raises:
        ------
            ProviderNonRetryableError: Don't retry the request
            ProviderRetryableError: Retry the request

        Returns:
        -------
            str: A reference identifier for the sent notification

        """
        publish_params = {'Message': push_model.message}
        if push_model.target_arn is not None:
            publish_params['TargetArn'] = push_model.target_arn
        else:
            publish_params['TopicArn'] = push_model.topic_arn  # type: ignore

        try:
            session = get_session()
            async with session.create_client(
                'sns',
                region_name=os.getenv('AWS_REGION_NAME', 'us-east-1'),
                aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY', ''),
                aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID', ''),
            ) as client:
                response: dict[str, str] = await client.publish(**publish_params)
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] in sns_publish_retriable_exceptions_set:
                raise ProviderRetryableError from e

            raise ProviderNonRetryableError from e
        except Exception as e:
            raise ProviderNonRetryableError from e

        logger.debug(response)
        return response['MessageId']

    async def register_push_endpoint(self, push_registration_model: PushRegistrationModel) -> str:
        """Register a mobile app user.

        https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/sns/client/create_platform_endpoint.html

        Args:
        ----
            push_registration_model: the parameters to pass to SNS.Client.create_platform_endpoint

        Returns:
        -------
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
        except Exception:
            logger.exception('Failed to register a push client with AWS SNS: %s', push_registration_model)
            raise

        logger.info(
            'Created push endpoint ARN %s for device %s on application %s.',
            response['EndpointArn'],
            push_registration_model.token,
            push_registration_model.platform_application_arn,
        )
        return response['EndpointArn']
