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
    SqsAsyncProducer,
    SqsAsyncProducer0,
)

TEST_QUEUE_NAME = 'test_queue'


@pytest.fixture
def setup_queue(mock_boto: Generator) -> None:
    """Set up the SQS queue for testing."""
    # Create a mock SQS queue
    sqs_client = botocore.session.get_session().create_client(
        'sqs', region_name=AWS_REGION, aws_access_key_id=AWS_ACCESS_KEY_ID, aws_secret_access_key=AWS_SECRET_ACCESS_KEY
    )
    sqs_client.create_queue(QueueName=TEST_QUEUE_NAME)


class TestSqsAsyncProducer:
    """Test the SQS async producer."""

    @staticmethod
    def test_sqs_producer_str(mock_boto) -> None:
        """Test the string representation of the SqsAsyncProducer."""
        client = SqsAsyncProducer()
        assert str(client) == 'AWS SQS Producer Client', 'String representation should match'

    @staticmethod
    async def test_sqs_producer_send_message(setup_queue) -> None:
        """Test the send_message method of the SqsAsyncProducer."""
        producer = SqsAsyncProducer()
        response = await producer.enqueue_message(TEST_QUEUE_NAME, 'test_message')
        assert isinstance(response, dict), 'send_message should return a dictionary'
        assert 'MessageId' in response, 'Response should contain MessageId'

    @staticmethod
    async def test_sqs_producer_send_message_invalid_queue(mock_boto) -> None:
        """Test sending a message to an invalid queue."""
        producer = SqsAsyncProducer()
        with pytest.raises(NonRetryableError):
            await producer.enqueue_message('invalid_queue', 'test_message')

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
