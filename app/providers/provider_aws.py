import os

import botocore
from aiobotocore.session import get_session

from app.providers import sns_publish_retriable_exceptions_set
from app.providers.provider_base import ProviderBase, ProviderNonRetryableError, ProviderRetryableError
from app.providers.provider_schemas import PushModel


class ProviderAWS(ProviderBase):
    """
    This is the provider interface for Amazon Web Services (AWS).
    """

    async def _send_push(self, push_model: PushModel) -> str:
        """
        Sends a message to an Amazon SNS topic.  Return a reference string.

        https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/sns/client/publish.html
        """

        # The AWS SNS "publish" method (called below) does not accept parameters set to None.
        publish_params = push_model.model_dump()
        del publish_params['TargetArn' if (push_model.TargetArn is None) else 'TopicArn']

        try:
            session = get_session()
            async with session.create_client(
                'sns',
                region_name=os.getenv('AWS_REGION_NAME', 'us-east-1'),
                aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY', ''),
                aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID', '')
            ) as client:
                response = await client.publish(**publish_params)
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] in sns_publish_retriable_exceptions_set:
                raise ProviderRetryableError from e

            raise ProviderNonRetryableError from e
        except Exception as e:
            raise ProviderNonRetryableError from e

        return response['MessageId']
