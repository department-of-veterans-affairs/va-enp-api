"""Shared test utilities for REST API tests."""

from typing import TYPE_CHECKING, Callable, Dict
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from pytest_mock import MockerFixture

from app.clients.redis_client import RedisClientManager

if TYPE_CHECKING:
    from tests.conftest import ENPTestClient


class RedisTestHelper:
    """Helper class for setting up Redis mocks consistently across tests."""

    @staticmethod
    def mock_redis_success() -> Mock:
        """Create a Redis mock that allows all rate limit requests.

        Returns:
            Mock: A mocked RedisClientManager that returns True for consume_rate_limit_token.
        """
        mock_redis = Mock(spec=RedisClientManager)
        mock_redis.consume_rate_limit_token = AsyncMock(return_value=True)
        return mock_redis

    @staticmethod
    def mock_redis_rate_limited() -> Mock:
        """Create a Redis mock that blocks all rate limit requests.

        Returns:
            Mock: A mocked RedisClientManager that returns False for consume_rate_limit_token.
        """
        mock_redis = Mock(spec=RedisClientManager)
        mock_redis.consume_rate_limit_token = AsyncMock(return_value=False)
        return mock_redis

    @staticmethod
    def mock_context_for_rate_limiting() -> Dict[str, str]:
        """Create a consistent context mock for rate limiting tests.

        Returns:
            Dict[str, str]: A context dictionary with request_id, service_id, and api_key_id.
        """
        return {
            'request_id': str(uuid4()),
            'service_id': str(uuid4()),
            'api_key_id': str(uuid4()),
        }


class AuthTestHelper:
    """Helper class for setting up authentication mocks consistently."""

    @staticmethod
    def bypass_auth(mocker: MockerFixture) -> None:
        """Bypass authentication for testing API endpoints.

        Args:
            mocker: The pytest mocker fixture.
        """
        mocker.patch('app.auth.verify_service_token')

    @staticmethod
    def setup_rate_limiting_mocks(mocker: MockerFixture, client: 'ENPTestClient', rate_limited: bool = False) -> None:
        """Set up complete rate limiting mocks for API tests.

        Args:
            mocker: The pytest mocker fixture
            client: The test client
            rate_limited: Whether to simulate rate limiting (default: False)
        """
        # Mock context
        mock_context = RedisTestHelper.mock_context_for_rate_limiting()
        mocker.patch('app.limits.context', mock_context)

        # Mock Redis client
        if rate_limited:
            mock_redis = RedisTestHelper.mock_redis_rate_limited()
        else:
            mock_redis = RedisTestHelper.mock_redis_success()

        mocker.patch.object(client.app.enp_state, 'redis_client_manager', mock_redis)


@pytest.fixture
def redis_helper() -> RedisTestHelper:
    """Provide Redis test helper as a fixture.

    Returns:
        RedisTestHelper: An instance of the Redis test helper class.
    """
    return RedisTestHelper()


@pytest.fixture
def auth_helper() -> AuthTestHelper:
    """Provide Auth test helper as a fixture.

    Returns:
        AuthTestHelper: An instance of the Auth test helper class.
    """
    return AuthTestHelper()


@pytest.fixture
def api_test_setup() -> Callable[[MockerFixture, 'ENPTestClient', bool], None]:
    """Fixture that provides a complete API test setup function.

    Returns:
        A function that takes (mocker, client, rate_limited) and sets up all necessary mocks
    """

    def _setup(mocker: MockerFixture, client: 'ENPTestClient', rate_limited: bool = False) -> None:
        AuthTestHelper.bypass_auth(mocker)
        AuthTestHelper.setup_rate_limiting_mocks(mocker, client, rate_limited)

    return _setup
