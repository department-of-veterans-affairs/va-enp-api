"""Test the SQS client found in app/legacy/clients/sqs.py."""

from typing import Any, Generator, cast
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import botocore
import pytest
from botocore.exceptions import ClientError
from types_aiobotocore_sqs import SQSClient
from types_boto3_sqs import SQSClient as SQSClientBoto3

from app.constants import AWS_REGION, QUEUE_PREFIX
from app.exceptions import NonRetryableError, RetryableError
from app.legacy.clients.sqs import CeleryTaskEnvelope, SqsAsyncProducer

TEST_QUEUE_NAME = 'test_queue'
TEST_QUEUE_WITH_PREFIX = f'{QUEUE_PREFIX}test_queue'


@pytest.fixture
def setup_queue(moto_server: Generator[None, Any, None]) -> Generator[Any | str, Any, None]:
    """Set up the SQS queue for testing.

    Yields:
        str: The URL of the created SQS queue.
    """
    # Create a mock SQS queue, casting required by mypy
    sqs_client = cast(
        SQSClientBoto3,
        botocore.session.get_session().create_client('sqs', region_name=AWS_REGION),
    )

    test_queue = sqs_client.create_queue(QueueName=TEST_QUEUE_WITH_PREFIX)

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
    @pytest.mark.parametrize(
        'test_tasks',
        [
            [(TEST_QUEUE_NAME, ('task_name', uuid4()))],
            [(TEST_QUEUE_NAME, ('task_name', uuid4())), ('another_queue', ('task2_name', uuid4()))],
        ],
        ids=[
            'single_task',
            'multiple_tasks',
        ],
    )
    async def test_enqueue_message(
        setup_queue: None,
        test_tasks: list[tuple[str, tuple[str, UUID]]],
    ) -> None:
        """Test the enqueue_message method of the SqsAsyncProducer."""
        producer = SqsAsyncProducer()

        await producer.enqueue_message(test_tasks)

    @staticmethod
    async def test_exception_raised_in_enqueue_message(
        moto_server: Generator[None, Any, None],
        mocker: AsyncMock,
    ) -> None:
        """Test the enqueue_message method of the SqsAsyncProducer."""
        mock_logger = mocker.patch('app.legacy.clients.sqs.logger.exception')
        notification_id = uuid4()
        producer = SqsAsyncProducer()

        # exception raised because queue not found
        await producer.enqueue_message([('invalid_queue', ('task_name', notification_id))])

        assert mock_logger.call_count == 2
        mock_logger.assert_called_with('Failed to enqueue task(s) for notification {}', notification_id)

    @staticmethod
    async def test_enqueue_message_private(setup_queue: None) -> None:
        """Test the enqueue_message method of the SqsAsyncProducer."""
        producer = SqsAsyncProducer()
        response = await producer._enqueue_message(TEST_QUEUE_WITH_PREFIX, 'test_message')
        assert isinstance(response, dict), 'enqueue_message should return a dictionary'
        assert 'MessageId' in response, 'Response should contain MessageId'

    @staticmethod
    async def test_enqueue_message_invalid_queue(moto_server: Generator[None, Any, None]) -> None:
        """Test sending a message to an invalid queue."""
        producer = SqsAsyncProducer()
        with pytest.raises(NonRetryableError):
            await producer._enqueue_message('invalid_queue', 'test_message')

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


class TestSqsAscyncProducerGenerateTasks:
    """Test the SqsAsyncProducer task envelope generation methods."""

    @staticmethod
    def test_generate_celery_task_fields() -> None:
        """Test the generate_celery_task function returns the expected envelope structure."""
        producer = SqsAsyncProducer()
        test_args = ('task_name', uuid4())

        # mimicing how the task is called in the app
        result: CeleryTaskEnvelope = producer._generate_celery_task(TEST_QUEUE_NAME, *test_args)

        assert isinstance(result, dict), 'Result should be a CeleryTaskEnvelope instance'
        assert 'body' in result
        assert 'properties' in result
        assert result['properties']['delivery_info']['routing_key'] == TEST_QUEUE_WITH_PREFIX
        assert result['content-type'] == 'application/json'

    @staticmethod
    def test_generate_celery_task_chain() -> None:
        """Test the generate_celery_task_chain function returns the expected envelope structure."""
        producer = SqsAsyncProducer()
        task1_name = 'task_name'
        task2_name = 'task2_name'
        test_tasks = [
            (TEST_QUEUE_NAME, (task1_name, uuid4())),
            ('another_queue', (task2_name, uuid4())),
        ]

        # mimicing how the task is called in the app
        result: CeleryTaskEnvelope = producer._generate_celery_task_chain(test_tasks)

        assert isinstance(result, dict), 'Result should be a CeleryTaskEnvelope instance'
        assert 'body' in result
        assert 'properties' in result
        assert result['properties']['delivery_info']['routing_key'] == TEST_QUEUE_WITH_PREFIX
        assert result['headers']['task'] == task1_name
        assert len(result['headers']['chain']) == 1
        assert result['headers']['chain'][0]['task'] == task2_name

    @staticmethod
    def test_generate_celery_task_chain_with_3_tasks() -> None:
        """Test the generate_celery_task_chain function returns the expected envelope structure."""
        producer = SqsAsyncProducer()
        task1_name = 'task_name'
        task2_name = 'task2_name'
        task3_name = 'task3_name'
        test_tasks = [
            (TEST_QUEUE_NAME, (task1_name, uuid4())),
            ('another_queue', (task2_name, uuid4())),
            ('third_queue', (task3_name, uuid4())),
        ]

        # mimicing how the task is called in the app
        result: CeleryTaskEnvelope = producer._generate_celery_task_chain(test_tasks)

        assert isinstance(result, dict), 'Result should be a CeleryTaskEnvelope instance'
        assert 'body' in result
        assert 'properties' in result
        assert result['properties']['delivery_info']['routing_key'] == TEST_QUEUE_WITH_PREFIX
        assert result['headers']['task'] == task1_name
        assert len(result['headers']['chain']) == 2

        # task order is reversed in the chain
        assert result['headers']['chain'][0]['task'] == task3_name
        assert result['headers']['chain'][1]['task'] == task2_name
