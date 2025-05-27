"""Test the SQS client found in app/legacy/clients/sqs.py."""

import uuid
from typing import Any, Generator, cast
from unittest.mock import AsyncMock

import botocore
import pytest
from botocore.exceptions import ClientError
from types_aiobotocore_sqs import SQSClient
from types_boto3_sqs import SQSClient as SQSClientBoto3

from app.exceptions import NonRetryableError, RetryableError
from app.legacy.clients.sqs import (
    AWS_ACCESS_KEY_ID,
    AWS_REGION,
    AWS_SECRET_ACCESS_KEY,
    SqsAsyncProducer,
)

TEST_QUEUE_NAME = 'test_queue'


@pytest.fixture
def setup_queue(moto_server: Generator[None, Any, None]) -> Generator[Any | str, Any, None]:
    """Set up the SQS queue for testing.

    Yields:
        str: The URL of the created SQS queue.
    """
    # Create a mock SQS queue, casting required by mypy
    sqs_client = cast(
        SQSClientBoto3,
        botocore.session.get_session().create_client(
            'sqs',
            region_name=AWS_REGION,
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        ),
    )

    test_queue = sqs_client.create_queue(QueueName=TEST_QUEUE_NAME)

    yield test_queue['QueueUrl']

    sqs_client.delete_queue(QueueUrl=test_queue['QueueUrl'])


# DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version.
# Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
@pytest.mark.filterwarnings('ignore::DeprecationWarning')
class TestSqsAsyncProducer:
    """Test the SQS async producer."""

    @staticmethod
    def test_sqs_producer_str(moto_server: Generator[None, Any, None]) -> None:
        """Test the string representation of the SqsAsyncProducer."""
        client = SqsAsyncProducer()
        assert str(client) == 'AWS SQS Producer Client', 'String representation should match'

    @staticmethod
    async def test_sqs_producer_send_message(setup_queue: None) -> None:
        """Test the send_message method of the SqsAsyncProducer."""
        producer = SqsAsyncProducer()
        response = await producer.enqueue_message(TEST_QUEUE_NAME, 'test_message')
        assert isinstance(response, dict), 'send_message should return a dictionary'
        assert 'MessageId' in response, 'Response should contain MessageId'

    @staticmethod
    async def test_sqs_producer_send_message_invalid_queue(moto_server: Generator[None, Any, None]) -> None:
        """Test sending a message to an invalid queue."""
        producer = SqsAsyncProducer()
        with pytest.raises(NonRetryableError):
            await producer.enqueue_message('invalid_queue', 'test_message')

    @staticmethod
    async def test_get_queue_url_key_error() -> None:
        """Test the get_queue_url method raises a KeyError."""
        mock_sqs_client = AsyncMock(spec=SQSClient)
        mock_sqs_client.get_queue_url.return_value = {}

        producer = SqsAsyncProducer()
        with pytest.raises(NonRetryableError):
            await producer._get_queue_url(mock_sqs_client, 'q_name')

    @staticmethod
    async def test_get_queue_url_unexpected_error() -> None:
        """Test the get_queue_url method raises a NonRetryableError."""
        mock_sqs_client = AsyncMock(spec=SQSClient)
        mock_sqs_client.get_queue_url.side_effect = Exception('Unexpected error')

        producer = SqsAsyncProducer()
        with pytest.raises(NonRetryableError):
            await producer._get_queue_url(mock_sqs_client, 'q_name')

    @staticmethod
    async def test_send_message_to_queue_client_error(setup_queue: None) -> None:
        """Test sending an invalid message."""
        mock_sqs_client = AsyncMock(spec=SQSClient)
        mock_sqs_client.send_message.side_effect = ClientError(
            {'Error': {'Code': 'Test', 'Message': 'Invalid message'}}, 'send_message'
        )

        producer = SqsAsyncProducer()

        with pytest.raises(NonRetryableError):
            await producer._send_message_to_queue(mock_sqs_client, '', '', '')

    @staticmethod
    async def test_send_message_to_queue_unexpected_error(setup_queue: None) -> None:
        """Test sending a message raises a NonRetryableError."""
        mock_sqs_client = AsyncMock(spec=SQSClient)
        mock_sqs_client.send_message.side_effect = Exception('Unexpected error')

        producer = SqsAsyncProducer()

        with pytest.raises(NonRetryableError):
            await producer._send_message_to_queue(mock_sqs_client, '', '', 'test_message')

    @staticmethod
    @pytest.mark.parametrize(
        ('error_code', 'expected_exception'),
        [
            ('ThrottlingException', RetryableError),
            ('RequestTimeout', RetryableError),
            ('ServiceUnavailable', RetryableError),
            ('InvalidParameterValue', NonRetryableError),
        ],
        ids=[
            'ThrottlingException',
            'RequestTimeout',
            'ServiceUnavailable',
            'InvalidParameterValue',
        ],
    )
    async def test_handle_client_error_throws_expected_exception(
        error_code: str,
        expected_exception: type[Exception],  # NonRetryableError | RetryableError,
    ) -> None:
        """Test the _handle_client_error method throws a RetryableError or NonRetryableError."""
        # Set up a ClientError with the given error code
        error_response = {
            'Error': {
                'Code': error_code,
                'Message': 'Test error message',
            },
        }

        # importing _ClientErrorResponseTypeDef causes an error, so we must ignore the mypy error here
        client_error = ClientError(error_response=error_response, operation_name='test_operation')  # type: ignore[arg-type]

        with pytest.raises(expected_exception):
            SqsAsyncProducer._handle_client_error(client_error, 'Test error message')

    @staticmethod
    def test_generate_celery_task_fields() -> None:
        """Test the generate_celery_task function returns the expected envelope structure."""
        producer = SqsAsyncProducer()
        queue_name = 'test_q'
        test_args = ('task_name', uuid.uuid4())

        # mimicing how the task is called in the app
        result = producer.generate_celery_task(queue_name, *test_args)

        assert isinstance(result, dict)
        assert 'body' in result
        assert 'properties' in result
        assert result['properties']['delivery_info']['routing_key'] == queue_name
        assert result['content-type'] == 'application/json'
