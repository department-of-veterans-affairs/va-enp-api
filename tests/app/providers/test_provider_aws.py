"""Test module for app/providers/provider_aws.py."""

from unittest.mock import AsyncMock, patch

import botocore.exceptions
import pytest

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
            {'Message': 'This is a message.', 'TargetArn': 'This is an ARN.'},
            {'Message': 'This is a message.', 'TopicArn': 'This is an ARN.'},
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

        mock_client.publish.assert_called_once_with(**data)
        assert reference_id == 'message_id'

    async def test_send_push_notification_botocore_exceptions_not_retriable(self, mock_get_session: AsyncMock) -> None:
        """Other than ClientError, Botocore exceptions are client-side exceptions that should not result in a retry.

        Exceptions in the provider code should re-raise ProviderNonRetryableError or ProviderRetryableError.

        https://boto3.amazonaws.com/v1/documentation/api/latest/guide/error-handling.html
        """
        mock_client = AsyncMock()
        mock_get_session.return_value.create_client.return_value.__aenter__.return_value = mock_client
        push_model = PushModel(Message='', TargetArn='')

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
        ('exc', 'should_retry'),
        [
            ('InvalidParameterException', False),
            ('InvalidParameterValueException', False),
            ('InternalErrorException', True),
            ('NotFoundException', False),
            ('EndpointDisabledException', True),
            ('PlatformApplicationDisabledException', True),
            ('AuthorizationErrorException', False),
            ('KMSDisabledException', True),
            ('KMSInvalidStateException', True),
            ('KMSNotFoundException', False),
            ('KMSOptInRequired', False),
            ('KMSThrottlingException', True),
            ('KMSAccessDeniedException', False),
            ('InvalidSecurityException', False),
            ('ValidationException', False),
        ],
    )
    async def test_send_push_notification_ClientError_exceptions(
        self, mock_get_session: AsyncMock, exc: str, should_retry: bool
    ) -> None:
        """Some instances of ClientError should result in a retry.

        Exceptions in the provider code should re-raise ProviderNonRetryableError or ProviderRetryableError.

        The AWS provider uses SNS to send push notifications.  The tested exceptions are the exceptions
        that might get raised via calling the SNS client's "publish" method.

        https://boto3.amazonaws.com/v1/documentation/api/latest/guide/error-handling.html
        https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/sns/client/publish.html
        """
        mock_client = AsyncMock()
        mock_get_session.return_value.create_client.return_value.__aenter__.return_value = mock_client
        push_model = PushModel(Message='', TargetArn='')

        # Initializing a ClientError requires the positional arguments "error_response" and "operation_name".
        mock_client.publish.side_effect = botocore.exceptions.ClientError({'Error': {'Code': exc}}, 'sns')

        if should_retry:
            with pytest.raises(ProviderRetryableError):
                await self.provider.send_notification(push_model)
        else:
            with pytest.raises(ProviderNonRetryableError):
                await self.provider.send_notification(push_model)
