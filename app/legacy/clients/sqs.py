"""Client that defines how to interact with SQS."""

import base64
import json
import os
import uuid

from aiobotocore.session import get_session
from botocore.exceptions import ClientError
from pydantic import UUID4

from app.exceptions import NonRetryableError, RetryableError
from app.logging.logging_config import logger

AWS_REGION = os.getenv('AWS_REGION_NAME', 'us-east-1')
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID', 'test')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY', 'test')


# based off aiobotocore example: https://github.com/aio-libs/aiobotocore/blob/master/examples/sqs_queue_producer.py
class SQSClient:
    """Client for AWS SQS."""

    def __new__(cls, *args, **kwargs) -> 'SQSClient':
        """Create a new instance of SQSClient.

        This method ensures that only one instance of SQSClient is created (singleton pattern).

        Returns:
            SQSClient: The singleton instance of SQSClient.
        """
        if not hasattr(cls, '_instance'):
            cls._instance = super(SQSClient, cls).__new__(cls)
            logger.debug('SQSClient instance created: {}', cls._instance)
        return cls._instance

    def __str__(self) -> str:
        """Return the name of the client."""
        return 'AWS SQS Client'

    def __init__(self) -> None:
        """Initialize the SQS client."""
        if hasattr(self, '_sqs_client_context'):
            logger.debug('SQSClient instance already exists, not recreating sqs client context.')
            return

        # Initialize the SQS client context
        self._sqs_client_context = get_session().create_client(
            'sqs',
            region_name=AWS_REGION,
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        )

    async def enqueue_message(self, queue_name: str, message: str) -> dict[str, str]:
        """Send a message to the specified SQS queue.

        Args:
            queue_name (str): The name of the SQS queue
            message (str): The message to send

        Returns:
            dict[str, str]: The response from SQS
        """
        logger.debug('Sending message to SQS queue: {} - message: {}', queue_name, message)

        async with self._sqs_client_context as sqs_client:
            queue_url = await self._get_queue_url(queue_name)

            logger.debug('SQS queue URL retrieved: {}', queue_url)

            try:
                response = await sqs_client.send_message(QueueUrl=queue_url, MessageBody=message)
            except ClientError as e:
                err_msg = f'Failed to send message to SQS queue "{queue_name}".'
                self._handle_client_error(e, err_msg)

        logger.debug('Message sent to SQS queue {} - ID {}', queue_name, response['MessageId'])

        return response

    async def _get_queue_url(self, queue_name: str) -> str:
        """Get the URL of the specified SQS queue.

        Args:
            queue_name (str): The name of the SQS queue

        Returns:
            str: The URL of the SQS queue

        Raises:
            NonRetryableError: If the queue URL cannot be retrieved
        """
        async with self._sqs_client_context as sqs_client:
            try:
                response = await sqs_client.get_queue_url(QueueName=queue_name)
                q_url = response['QueueUrl']

            except ClientError as e:
                err_msg = f'Failed to get SQS queue URL for "{queue_name}".'
                self._handle_client_error(e, err_msg)

            except KeyError as e:
                err_msg = f'QueueUrl not found in response: {response}'
                logger.exception(err_msg)
                raise NonRetryableError(err_msg) from e

        return q_url

    @staticmethod
    def _handle_client_error(error: ClientError, err_msg: str) -> None:
        """Handle ClientError exceptions.

        Args:
            error (ClientError): The ClientError to handle
            err_msg (str): The error message to log and include in the exception

        Raises:
            NonRetryableError: If the error is non-retryable
            RetryableError: If the error is retryable
        """
        error_code = error.response.get('Error', {}).get('Code')

        if error_code in {'ThrottlingException', 'RequestTimeout', 'ServiceUnavailable'}:
            err_msg += ' ClientError: Retryable'
            logger.exception(err_msg)
            raise RetryableError(err_msg) from error
        else:
            err_msg += ' ClientError: NonRetryable'
            logger.exception(err_msg)
            raise NonRetryableError(err_msg) from error


# TODO: Make this more generic
def generate_celery_task(
    queue_name: str, task_name: str, notification_id: UUID4
) -> dict[str, str | dict[str, int | str | dict[str, int | str]]]:
    """A celery task envelope is created.

    The envelope has a generic schema that can be consumed before it routes to a celery task.
    The task is used to route the message to the proper celery method in the flask app (napi).

    Args:
        queue_name (str): The name of the SQS queue
        task_name (str): The name of the task to be executed
        notification_id (UUID4): The ID of the notification

    Returns:
        dict[str, str | dict[str, int | str | dict[str, int | str]]]: The envelope containing the task body and properties
    """
    task_body = {
        'task': task_name,
        'id': str(uuid.uuid4()),
        'args': [str(notification_id)],
        'kwargs': {},
    }
    envelope = {
        'body': base64.b64encode(bytes(json.dumps(task_body), 'utf-8')).decode('utf-8'),
        'content-encoding': 'utf-8',
        'content-type': 'application/json',
        'headers': {},
        'properties': {
            'reply_to': str(uuid.uuid4()),
            'correlation_id': str(uuid.uuid4()),
            'delivery_mode': 2,
            'delivery_info': {'priority': 0, 'exchange': 'default', 'routing_key': queue_name},
            'body_encoding': 'base64',
            'delivery_tag': str(uuid.uuid4()),
        },
    }

    return envelope
