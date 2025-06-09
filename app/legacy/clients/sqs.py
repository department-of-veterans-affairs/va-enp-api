"""Client that defines how to interact with SQS."""

import base64
import json
from typing import Any, NotRequired, TypedDict
from uuid import uuid4

from aiobotocore.session import ClientCreatorContext, get_session
from async_lru import alru_cache
from botocore.exceptions import ClientError
from pydantic import UUID4
from types_aiobotocore_sqs import SQSClient
from types_aiobotocore_sqs.type_defs import SendMessageResultTypeDef

from app.constants import AWS_REGION, QUEUE_PREFIX, TWELVE_HOURS
from app.exceptions import NonRetryableError, RetryableError
from app.legacy.clients.utils import client_retry
from app.logging.logging_config import logger


class CeleryTaskDict(TypedDict):
    """Dictionary representing a Celery task."""

    task: str
    id: str
    args: list[str]
    kwargs: dict[str, str]
    options: dict[str, str]
    subtask_type: None
    immutable: bool


class DeliveryInfoDict(TypedDict):
    """Delivery information for the message sent to SQS."""

    priority: int
    exchange: str
    routing_key: str


class PropertiesDict(TypedDict):
    """Properties of the message sent to SQS."""

    reply_to: NotRequired[str]
    correlation_id: str
    delivery_mode: int
    delivery_info: DeliveryInfoDict
    body_encoding: str
    delivery_tag: str


class CeleryHeaderDict(TypedDict):
    """Headers for the Celery task envelope."""

    lang: str
    task: str
    id: str
    root_id: str
    chain: list[CeleryTaskDict]


# Defined without using a class to enable proper keys (keys contain hyphens)
CeleryTaskEnvelope = TypedDict(
    'CeleryTaskEnvelope',
    {
        'body': str,
        'content-encoding': str,
        'content-type': str,
        # headers can be an empty dict or a CeleryHeaderDict
        'headers': CeleryHeaderDict | dict[Any, Any],
        'properties': PropertiesDict,
    },
)


# based off aiobotocore example: https://github.com/aio-libs/aiobotocore/blob/master/examples/sqs_queue_producer.py
class SqsAsyncProducer:
    """Client for AWS SQS."""

    def __init__(self) -> None:
        """Initialize the SQS client."""
        self._client: 'ClientCreatorContext[SQSClient]' | None = None

    def __str__(self) -> str:
        """Return the name of the client."""
        return 'AWS SQS Producer Client'

    @property
    def sqs_client_context(self) -> 'ClientCreatorContext[SQSClient]':
        """Get the SQS client context.

        Returns:
            ClientCreatorContext: The SQS client context
        """
        # Initialize the SQS client context
        if self._client is None:
            self._client = get_session().create_client(
                'sqs',
                region_name=AWS_REGION,
            )

        return self._client

    async def enqueue_message(self, tasks: list[tuple[str, tuple[str, UUID4]]]) -> None:
        """Enqueue multiple messages to SQS.

        Args:
            tasks (list[tuple[str, tuple[str, UUID4]]]): List of tuples containing queue name and task details
        """
        queue_name = ''
        if len(tasks) == 1:
            # build body for 1 task
            queue_name, (task_name, notification_id) = tasks[0]
            task_envelope = json.dumps(self._generate_celery_task(queue_name, task_name, notification_id))
        else:
            # build body for multiple tasks
            # get the first queue name
            queue_name = tasks[0][0]
            task_envelope = json.dumps(self._generate_celery_task_chain(tasks))

        queue_name = f'{QUEUE_PREFIX}{queue_name}'

        try:
            await self._enqueue_message(
                queue_name=queue_name,
                message=task_envelope,
            )
        except (RetryableError, NonRetryableError):
            logger.exception('Failed to enqueue notification task(s).')

    async def _enqueue_message(
        self,
        queue_name: str,
        message: str,
    ) -> SendMessageResultTypeDef:
        """Send a message to the specified SQS queue.

        Args:
            queue_name (str): The name of the SQS queue
            message (str): The message to send

        Returns:
            SendMessageResultTypeDef: The response from SQS
        """
        logger.debug('Sending message to SQS queue: {} - message: {}', queue_name, message)

        async with self.sqs_client_context as sqs_client:
            queue_url = await self._get_queue_url(sqs_client, queue_name)

            logger.debug('SQS queue URL retrieved: {}', queue_url)

            response = await self._send_message_to_queue(sqs_client, queue_name, queue_url, message)

        logger.debug('Message sent to SQS queue {} - message ID {}', queue_name, response.get('MessageId'))

        return response

    @client_retry
    @alru_cache(maxsize=1024, ttl=TWELVE_HOURS)
    async def _get_queue_url(
        self,
        sqs_client: SQSClient,
        queue_name: str,
    ) -> str:
        """Get the URL of the specified SQS queue.

        Args:
            sqs_client (SQSClient): The SQS client
            queue_name (str): The name of the SQS queue

        Returns:
            str: The URL of the SQS queue

        Raises:
            NonRetryableError: If the queue URL cannot be retrieved
        """
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

        except Exception as e:
            err_msg = f'Unexpected error occurred while getting SQS queue URL for "{queue_name}".'
            logger.exception(err_msg)
            raise NonRetryableError(err_msg) from e

        return q_url

    @client_retry
    async def _send_message_to_queue(
        self,
        sqs_client: SQSClient,
        queue_name: str,
        queue_url: str,
        message: str,
    ) -> SendMessageResultTypeDef:
        """Send a message to the specified SQS queue.

        Args:
            sqs_client (SQSClient): The SQS client
            queue_name (str): The name of the SQS queue
            queue_url (str): The URL of the SQS queue
            message (str): The message to send

        Returns:
            SendMessageResultTypeDef: The response from SQS

        Raises:
            NonRetryableError: If the message cannot be sent
        """
        try:
            response = await sqs_client.send_message(QueueUrl=queue_url, MessageBody=message)

        except ClientError as e:
            err_msg = f'Failed to send message to SQS queue "{queue_name}".'
            self._handle_client_error(e, err_msg)

        except Exception as e:
            err_msg = f'Unexpected error occurred while sending message to SQS queue "{queue_name}".'
            logger.exception(err_msg)
            raise NonRetryableError(err_msg) from e

        return response

    @staticmethod
    def _handle_client_error(
        error: ClientError,
        err_msg: str,
    ) -> None:
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
    def _generate_celery_task(
        queue_name: str,
        task_name: str,
        notification_id: UUID4,
    ) -> CeleryTaskEnvelope:
        """Create a celery task envelope.

        The task is used to route the message to the proper celery method in the flask app (napi).

        Args:
            queue_name (str): The name of the SQS queue
            task_name (str): The name of the task to be executed
            notification_id (UUID4): The ID of the notification

        Returns:
            CeleryTaskEnvelope: The dictionary envelope containing the task body and properties
        """
        # add prefix to queue name
        queue_name = f'{QUEUE_PREFIX}{queue_name}'
        task_body = {
            'task': task_name,
            'id': str(uuid4()),
            'args': [str(notification_id)],
            'kwargs': {},
        }

        envelope: CeleryTaskEnvelope = {
            'body': base64.b64encode(bytes(json.dumps(task_body), 'utf-8')).decode('utf-8'),
            'content-encoding': 'utf-8',
            'content-type': 'application/json',
            'headers': {},
            'properties': PropertiesDict(
                reply_to=str(uuid4()),
                correlation_id=str(uuid4()),
                delivery_mode=2,
                delivery_info=DeliveryInfoDict(
                    priority=0,
                    exchange='default',
                    routing_key=queue_name,
                ),
                body_encoding='base64',
                delivery_tag=str(uuid4()),
            ),
        }

        return envelope

    @staticmethod
    def _generate_celery_task_chain(tasks: list[tuple[str, tuple[str, UUID4]]]) -> CeleryTaskEnvelope:
        """Generate a celery task envelope for a celery task chain.

        Args:
            tasks (list[tuple[str, tuple[str, UUID4]]]): List of tuples containing queue name and task details

        Returns:
            CeleryTaskEnvelope: The envelope containing the task body and properties
        """
        # task order:
        # [lookup-va-profile-id-tasks(if non va profile id), lookup-contact-info-tasks, deliver_sms]

        first_queue_name, (first_task_name, first_notification_id) = tasks.pop(0)
        # add prefix to the first queue
        first_queue_with_prefix = f'{QUEUE_PREFIX}{first_queue_name}'

        # I'm not sure if this is necessary
        reply_to = str(uuid4())

        # build body for the first task
        first_task_body = CeleryTaskDict(
            task=first_task_name,
            id=str(uuid4()),
            args=[],
            kwargs={'notification_id': str(first_notification_id)},
            options={'queue': first_queue_with_prefix},
            subtask_type=None,
            immutable=True,
        )

        # reversed to set proper chain order, celery pops from the end of the list
        tasks.reverse()

        # create the task chain, a list of CeleryTaskDicts
        chain_tasks = [
            CeleryTaskDict(
                task=task_name,
                id=str(uuid4()),
                args=[],
                kwargs={'notification_id': str(notification_id)},
                options={
                    'queue': queue_name,
                    'task_id': str(uuid4()),
                    'reply_to': reply_to,
                },
                subtask_type=None,
                immutable=True,
            )
            for queue_name, (task_name, notification_id) in tasks
            if len(tasks) > 0
        ]

        # build the body used in the envelope
        envelope_body = [
            [],
            {'notification_id': str(first_notification_id)},
            {
                'callbacks': None,
                'errbacks': None,
                'chain': chain_tasks,
                'chord': None,
            },
        ]

        # create the envelope to send to SQS
        envelope: CeleryTaskEnvelope = {
            'body': base64.b64encode(bytes(json.dumps(envelope_body), 'utf-8')).decode('utf-8'),
            'content-encoding': 'utf-8',
            'content-type': 'application/json',
            'headers': CeleryHeaderDict(
                lang='py',
                task=first_task_body['task'],
                id=first_task_body['id'],
                root_id=first_task_body['id'],
                chain=chain_tasks,
            ),
            'properties': PropertiesDict(
                reply_to=reply_to,
                correlation_id=first_task_body['id'],
                delivery_mode=2,
                delivery_info=DeliveryInfoDict(priority=0, exchange='default', routing_key=first_queue_with_prefix),
                body_encoding='base64',
                delivery_tag=str(uuid4()),
            ),
        }

        return envelope
