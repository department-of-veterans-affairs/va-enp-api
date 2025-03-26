"""Test module for app/providers/provider_aws.py.

For a discussion of AWS error handling:
    https://boto3.amazonaws.com/v1/documentation/api/latest/guide/error-handling.html
"""

from unittest.mock import AsyncMock, patch

import botocore.exceptions
import pytest
from starlette_context import request_cycle_context
from tenacity import stop_after_attempt, wait_none

from app.constants import MobileAppType
from app.exceptions import NonRetryableError
from app.providers import sns_publish_retriable_exceptions_set
from app.providers.provider_aws import ProviderAWS
from app.providers.provider_schemas import DeviceRegistrationModel, PushModel, PushRegistrationModel
from tests.app.providers import botocore_exceptions_kwargs


@patch('app.providers.provider_aws.get_session')
class TestProviderAWS:
    """Test the methods of the ProviderAWS class."""

    provider = ProviderAWS()

    async def test_str(self, mock_get_session: AsyncMock) -> None:
        """Test the string representation of the class."""
        assert str(self.provider) == 'AWS Provider'

    async def test_get_platform_application_arn(
        self, mock_get_session: AsyncMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test with various mocked environments."""
        monkeypatch.setenv('AWS_REGION_NAME', 'us-west-1')
        monkeypatch.setenv('AWS_ACCOUNT_ID', '999999999999')
        monkeypatch.setenv('AWS_PLATFORM', 'APNS')

        assert self.provider.get_platform_application_arn('foo') == 'arn:aws:sns:us-west-1:999999999999:app/APNS/foo'

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

    @pytest.mark.parametrize(('name', 'exc'), [(n, e) for n, e in botocore.exceptions.__dict__.items()])
    async def test_send_push_notification_botocore_exceptions_not_retriable(
        self, mock_get_session: AsyncMock, name: str, exc: botocore.exceptions.BotoCoreError
    ) -> None:
        """Other than ClientError, Botocore exceptions are client-side exceptions that should not result in a retry.

        Exceptions in the provider code should re-raise NonRetryableError or RetryableError.
        """
        mock_client = AsyncMock()
        mock_get_session.return_value.create_client.return_value.__aenter__.return_value = mock_client
        push_model = PushModel(message='', target_arn='')

        raise_exc: bool = True
        if not isinstance(exc, type) or name in ('ClientError', 'EventStreamError'):
            # ClientErrors might be retriable, and there doesn't seem to be an obvious way to mock an EventStreamError.
            raise_exc = False
        elif name == 'WaiterError':
            # Initializing this exception requires positional arguments.
            mock_client.publish.side_effect = exc('', '', '')
        elif name in botocore_exceptions_kwargs:
            # Initializing these exceptions requires keyword arguments.
            mock_client.publish.side_effect = exc(**{key: '' for key in botocore_exceptions_kwargs[name]})
        else:
            mock_client.publish.side_effect = exc()

        if raise_exc:
            with pytest.raises(NonRetryableError):
                await self.provider.send_notification(push_model)
        else:
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
        """These instances of ClientError should raise NonRetryableError.

        The AWS provider uses SNS to send push notifications.  The tested exceptions are exceptions
        that might get raised via calling the SNS client's "publish" method.

        https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/sns/client/publish.html
        """
        mock_client = AsyncMock()
        mock_get_session.return_value.create_client.return_value.__aenter__.return_value = mock_client
        push_model = PushModel(message='', target_arn='')

        # Initializing a ClientError requires the positional arguments "error_response" and "operation_name".
        mock_client.publish.side_effect = botocore.exceptions.ClientError({'Error': {'Code': exc}}, 'sns')

        with pytest.raises(NonRetryableError):
            await self.provider.send_notification(push_model)

    @pytest.mark.parametrize('exc', list(sns_publish_retriable_exceptions_set))
    async def test_send_push_notification_ClientError_exceptions_retriable(
        self,
        mock_get_session: AsyncMock,
        exc: str,
    ) -> None:
        """These instances of ClientError should raise RetryableError.

        The AWS provider uses SNS to send push notifications. The tested exceptions are exceptions
        that might get raised via calling the SNS client's "publish" method.

        https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/sns/client/publish.html
        """
        mock_client = AsyncMock()
        mock_get_session.return_value.create_client.return_value.__aenter__.return_value = mock_client
        push_model = PushModel(message='', target_arn='')

        # Initializing a ClientError requires the positional arguments "error_response" and "operation_name".
        mock_client.publish.side_effect = botocore.exceptions.ClientError({'Error': {'Code': exc}}, 'sns')

        # This is returning None because it continues to retry until failure.
        # A str would be returned if calling _send_push was successful.
        # Using retry_with is necessary to avoid performing retries with the default wait strategy.
        assert (
            await self.provider.send_notification.retry_with(stop=stop_after_attempt(2), wait=wait_none())(  # type: ignore
                self.provider,
                push_model,
            )
            is None
        )

    async def test_register_push_endpoint(self, mock_get_session: AsyncMock) -> None:
        """Test the happy path.

        Tests for PushRegistrationModel ensure the rejection of invalid data.  There are no negative tests
        for this feature because exceptions are just logged and re-raised.
        """
        mock_client = AsyncMock()
        mock_client.create_platform_endpoint.return_value = {'EndpointArn': '12345'}
        mock_get_session.return_value.create_client.return_value.__aenter__.return_value = mock_client

        push_registration_model = PushRegistrationModel(platform_application_arn='123', token='456')
        assert await self.provider.register_push_endpoint(push_registration_model) == '12345'
        mock_client.create_platform_endpoint.assert_called_once()

    async def test_register_push_endpoint_with_retryable_exceptions(self, mock_get_session: AsyncMock) -> None:
        """Test handling of retryable exceptions."""
        mock_get_session.side_effect = botocore.exceptions.ClientError(
            {'Error': {'Code': 'InternalErrorException'}},
            'sns',
        )

        push_registration_model = PushRegistrationModel(platform_application_arn='123', token='456')

        # This is returning None because it continues to retry until failure.
        # A str would be returned if calling register_push_endpoint was successful.
        # Using retry_with is necessary to avoid performing retries with the default wait strategy.
        assert (
            await self.provider.register_push_endpoint.retry_with(stop=stop_after_attempt(2), wait=wait_none())(  # type: ignore
                self.provider, push_registration_model
            )
            is None
        )

    async def test_register_push_endpoint_with_non_retryable_exceptions(self, mock_get_session: AsyncMock) -> None:
        """Test handling of non-retryable exceptions."""
        mock_get_session.side_effect = botocore.exceptions.ClientError(
            {'Error': {'Code': 'InvalidParameterException'}},
            'sns',
        )

        push_registration_model = PushRegistrationModel(platform_application_arn='123', token='456')
        with pytest.raises(NonRetryableError):
            await self.provider.register_push_endpoint(push_registration_model)

    async def test_register_device(self, mock_get_session: AsyncMock) -> None:
        """Test the happy path."""
        mock_client = AsyncMock()
        mock_client.create_platform_endpoint.return_value = {
            'EndpointArn': 'arn:aws:sns:us-east-1:000000000000:app/APNS/12345',
        }
        mock_get_session.return_value.create_client.return_value.__aenter__.return_value = mock_client

        with request_cycle_context({'X-Request-ID': '123'}):
            actual = await self.provider.register_device(
                DeviceRegistrationModel(
                    platform_application_name=MobileAppType.VA_FLAGSHIP_APP,
                    token='bar',
                )
            )
        assert actual == 'arn:aws:sns:us-east-1:000000000000:app/APNS/12345'
