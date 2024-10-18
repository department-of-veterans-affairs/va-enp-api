"""Test module for app/providers/provider_aws.py."""

from unittest.mock import AsyncMock, patch

import botocore.exceptions
import pytest

from app.providers import sns_publish_retriable_exceptions_set
from app.providers.provider_aws import ProviderAWS
from app.providers.provider_base import ProviderNonRetryableError, ProviderRetryableError
from app.providers.provider_schemas import PushModel
from tests.app.providers import botocore_exceptions_kwargs


@pytest.mark.asyncio
@patch('app.providers.provider_aws.get_session')
class TestProviderAWS:
    """Test the methods of the ProviderAWS class."""

    provider = ProviderAWS()

    @pytest.mark.parametrize(
        'data',
        [
            {'message': 'This is a message.', 'target_arn': 'This is an ARN.'},
            {'message': 'This is a message.', 'topic_arn': 'This is an ARN.'},
        ],
        ids=(
            'target',
            'topic',
        ),
    )
    async def test_send_push_notification(self, mock_get_session: AsyncMock, data: dict[str, str]) -> None:
        """Test the happy path.

        Tests for PushModel ensure the rejection of invalid data.

        https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/sns/client/publish.html
        """
        mock_client = AsyncMock()
        mock_client.publish.return_value = {'MessageId': 'message_id', 'SequenceNumber': '12345'}
        mock_get_session.return_value.create_client.return_value.__aenter__.return_value = mock_client

        push_model = PushModel(**data)
        reference_id = await self.provider.send_notification(push_model)

        mock_client.publish.assert_called_once()
        assert reference_id == 'message_id'

    async def test_send_push_notification_botocore_exceptions_not_retriable(self, mock_get_session: AsyncMock) -> None:
        """Other than ClientError, Botocore exceptions are client-side exceptions that should not result in a retry.

        Exceptions in the provider code should re-raise ProviderNonRetryableError or ProviderRetryableError.

        https://boto3.amazonaws.com/v1/documentation/api/latest/guide/error-handling.html
        """
        mock_client = AsyncMock()
        mock_get_session.return_value.create_client.return_value.__aenter__.return_value = mock_client
        push_model = PushModel(message='', target_arn='')

        for name, exc in botocore.exceptions.__dict__.items():
            if not isinstance(exc, type) or name in ('ClientError', 'EventStreamError'):
                # ClientErrors might be retriable, and there doesn't seem to be an obvious way to mock
                # an EventStreamError.
                continue
            elif name == 'WaiterError':
                # Initializing this exception requires positional arguments.
                mock_client.publish.side_effect = exc('', '', '')
            elif name in botocore_exceptions_kwargs:
                # Initializing these exceptions requires keyword arguments.
                mock_client.publish.side_effect = exc(**{key: '' for key in botocore_exceptions_kwargs[name]})
            else:
                mock_client.publish.side_effect = exc()

            with pytest.raises(ProviderNonRetryableError):
                await self.provider.send_notification(push_model)

    @pytest.mark.parametrize(
        'exc',
        [
            'InvalidParameterException',
            'InvalidParameterValueException',
            'NotFoundException',
            'AuthorizationErrorException',
            'KMSNotFoundException',
            'KMSOptInRequired',
            'KMSAccessDeniedException',
            'InvalidSecurityException',
            'ValidationException',
        ],
    )
    async def test_send_push_notification_ClientError_exceptions_not_retriable(
        self, mock_get_session: AsyncMock, exc: str
    ) -> None:
        """These instances of ClientError should raise ProviderNonRetryableError.

        The AWS provider uses SNS to send push notifications.  The tested exceptions are exceptions
        that might get raised via calling the SNS client's "publish" method.

        https://boto3.amazonaws.com/v1/documentation/api/latest/guide/error-handling.html
        https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/sns/client/publish.html
        """
        mock_client = AsyncMock()
        mock_get_session.return_value.create_client.return_value.__aenter__.return_value = mock_client
        push_model = PushModel(message='', target_arn='')

        # Initializing a ClientError requires the positional arguments "error_response" and "operation_name".
        mock_client.publish.side_effect = botocore.exceptions.ClientError({'Error': {'Code': exc}}, 'sns')

        with pytest.raises(ProviderNonRetryableError):
            await self.provider.send_notification(push_model)

    @pytest.mark.parametrize('exc', list(sns_publish_retriable_exceptions_set))
    async def test_send_push_notification_ClientError_exceptions_retriable(
        self, mock_get_session: AsyncMock, exc: str
    ) -> None:
        """These instances of ClientError should raise ProviderRetryableError.

        The AWS provider uses SNS to send push notifications.  The tested exceptions are exceptions
        that might get raised via calling the SNS client's "publish" method.

        https://boto3.amazonaws.com/v1/documentation/api/latest/guide/error-handling.html
        https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/sns/client/publish.html
        """
        mock_client = AsyncMock()
        mock_get_session.return_value.create_client.return_value.__aenter__.return_value = mock_client
        push_model = PushModel(message='', target_arn='')

        # Initializing a ClientError requires the positional arguments "error_response" and "operation_name".
        mock_client.publish.side_effect = botocore.exceptions.ClientError({'Error': {'Code': exc}}, 'sns')

        with pytest.raises(ProviderRetryableError):
            await self.provider.send_notification(push_model)