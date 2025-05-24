"""Client that defines how to interact with SQS."""

import base64
import json
import os
from typing import Collection
from uuid import uuid4

from aiobotocore.session import ClientCreatorContext, get_session
from botocore.exceptions import ClientError, ParamValidationError
from pydantic import UUID4
from types_aiobotocore_sqs import SQSClient

from app.exceptions import NonRetryableError, RetryableError
from app.logging.logging_config import logger

AWS_REGION = os.getenv('AWS_REGION_NAME', 'us-east-1')
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID', 'test')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY', 'test')


# based off aiobotocore example: https://github.com/aio-libs/aiobotocore/blob/master/examples/sqs_queue_producer.py
class SqsAsyncProducer:
    """Client for AWS SQS."""

    def __init__(self) -> None:
        """Initialize the SQS client."""
        self._client: ClientCreatorContext | None = None

    def __str__(self) -> str:
        """Return the name of the client."""
        return 'AWS SQS Producer Client'

    @property
    def sqs_client_context(self) -> ClientCreatorContext:
        """Get the SQS client context.

        Returns:
            ClientCreatorContext: The SQS client context
        """
        # Initialize the SQS client context
        if self._client is None:
            self._client = get_session().create_client(
                'sqs',
                region_name=AWS_REGION,
                aws_access_key_id=AWS_ACCESS_KEY_ID,
                aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            )

        return self._client

    async def enqueue_message(
        self,
        queue_name: str,
        message: str,
    ) -> dict[str, str | dict[str, int | str | dict[str, int | str]]]:
        """Send a message to the specified SQS queue.

        Args:
            queue_name (str): The name of the SQS queue
            message (str): The message to send

        Returns:
            dict[str, str]: The response from SQS
        """
        logger.debug('Sending message to SQS queue: {} - message: {}', queue_name, message)

        async with self.sqs_client_context as sqs_client:
            queue_url = await self._get_queue_url(sqs_client, queue_name)

            logger.debug('SQS queue URL retrieved: {}', queue_url)

            response = await self._send_message_to_queue(sqs_client, queue_name, queue_url, message)

        logger.debug('Message sent to SQS queue {} - message ID {}', queue_name, response.get('MessageId'))

        return dict(response)

    async def _get_queue_url(self, sqs_client: SQSClient, queue_name: str) -> str:
        """Get the URL of the specified SQS queue.

        Args:
            sqs_client (SQSClient): The SQS client
            queue_name (str): The name of the SQS queue

        Returns:
            str: The URL of the SQS queue

        Raises:
            NonRetryableError: If the queue URL cannot be retrieved
        """
        # async with self.sqs_client_context as sqs_client:
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

    async def _send_message_to_queue(
        self, sqs_client: SQSClient, queue_name: str, queue_url: str, message: str
    ) -> dict[str, str]:
        """Send a message to the specified SQS queue.

        Args:
            sqs_client (SQSClient): The SQS client
            queue_name (str): The name of the SQS queue
            queue_url (str): The URL of the SQS queue
            message (str): The message to send

        Returns:
            dict[str, str]: The response from SQS

        Raises:
            NonRetryableError: If the message cannot be sent
        """
        try:
            response = await sqs_client.send_message(QueueUrl=queue_url, MessageBody=message)

        except ClientError as e:
            err_msg = f'Failed to send message to SQS queue "{queue_name}".'
            self._handle_client_error(e, err_msg)

        except ParamValidationError as e:
            err_msg = f'Invalid parameters for SQS queue "{queue_name}".'
            logger.exception(err_msg)
            raise NonRetryableError(err_msg) from e

        return dict(response)

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

    @staticmethod
    def generate_celery_task(queue_name: str, task_name: str, notification_id: UUID4) -> dict[str, Collection[str]]:
        """Create a celery task envelope.

        The task is used to route the message to the proper celery method in the flask app (napi).

        Args:
            queue_name (str): The name of the SQS queue
            task_name (str): The name of the task to be executed
            notification_id (UUID4): The ID of the notification

        Returns:
            dict[str, Collection[str]]: The envelope containing the task body and properties
        """
        task_body = {
            'task': task_name,
            'id': str(uuid4()),
            'args': [str(notification_id)],
            'kwargs': {},
        }
        envelope = {
            'body': base64.b64encode(bytes(json.dumps(task_body), 'utf-8')).decode('utf-8'),
            'content-encoding': 'utf-8',
            'content-type': 'application/json',
            'headers': {},
            'properties': {
                'reply_to': str(uuid4()),
                'correlation_id': str(uuid4()),
                'delivery_mode': 2,
                'delivery_info': {'priority': 0, 'exchange': 'default', 'routing_key': queue_name},
                'body_encoding': 'base64',
                'delivery_tag': str(uuid4()),
            },
        }

        return envelope
