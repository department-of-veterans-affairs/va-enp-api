"""Test the SQS client found in app/legacy/clients/sqs.py."""

import os
import uuid
from typing import Any, Generator

import botocore
import botocore.session
import pytest
from moto import server

from app.exceptions import NonRetryableError
from app.legacy.clients.sqs import (
    AWS_ACCESS_KEY_ID,
    AWS_REGION,
    AWS_SECRET_ACCESS_KEY,
    SQSClient,
    generate_celery_task,
)

TEST_QUEUE_NAME = 'test_queue'


@pytest.fixture
def mock_boto() -> Generator[None, Any, None]:
    """Set up a mock AWS server using Moto.

    See this StackOverflow answer for more details:
    https://stackoverflow.com/a/77490060
    """
    m_server = server.ThreadedMotoServer(port=0)

    m_server.start()
    port = m_server._server.socket.getsockname()[1]
    os.environ['AWS_ENDPOINT_URL'] = f'http://127.0.0.1:{port}'

    yield

    del os.environ['AWS_ENDPOINT_URL']
    m_server.stop()


@pytest.fixture
def setup_queue(mock_boto) -> None:
    """Set up the SQS queue for testing."""
    # Create a mock SQS queue
    sqs_client = botocore.session.get_session().create_client(
        'sqs', region_name=AWS_REGION, aws_access_key_id=AWS_ACCESS_KEY_ID, aws_secret_access_key=AWS_SECRET_ACCESS_KEY
    )
    sqs_client.create_queue(QueueName=TEST_QUEUE_NAME)


class TestSQSClient:
    """Test the SQS client found in app/legacy/clients/sqs.py."""

    @staticmethod
    def test_sqs_client_singleton(mock_boto) -> None:
        """Test that the SQSClient is a singleton."""
        client1 = SQSClient()
        client2 = SQSClient()
        assert client1 is client2, 'SQSClient should be a singleton'

    @staticmethod
    def test_sqs_client_str(mock_boto) -> None:
        """Test the string representation of the SQSClient."""
        client = SQSClient()
        assert str(client) == 'AWS SQS Client', 'String representation should match'

    @staticmethod
    def test_sqs_client_init(mock_boto) -> None:
        """Test the initialization of the SQSClient."""
        client = SQSClient()
        assert hasattr(client, '_sqs_client_context'), 'SQSClient should have a _sqs_client_context attribute'
        assert client._sqs_client_context is not None, '_sqs_client_context should not be None'

    @staticmethod
    async def test_sqs_client_send_message(setup_queue) -> None:
        """Test the send_message method of the SQSClient."""
        client = SQSClient()
        response = await client.enqueue_message(TEST_QUEUE_NAME, 'test_message')
        assert isinstance(response, dict), 'send_message should return a dictionary'
        assert 'MessageId' in response, 'Response should contain MessageId'

    @staticmethod
    async def test_sqs_client_send_message_invalid_queue(mock_boto) -> None:
        """Test sending a message to an invalid queue."""
        client = SQSClient()
        with pytest.raises(NonRetryableError):
            await client.enqueue_message('invalid_queue', 'test_message')


def test_generate_celery_task_fields() -> None:
    """Test the generate_celery_task function returns the expected envelope structure."""
    queue_name = 'test_q'
    test_args = ('task_name', uuid.uuid4())

    # mimicing how the task is called in the app
    result = generate_celery_task(queue_name, *test_args)

    assert isinstance(result, dict)
    assert 'body' in result
    assert 'properties' in result
    assert result['properties']['delivery_info']['routing_key'] == queue_name
    assert result['content-type'] == 'application/json'
