"""Test suite for initializing FastAPI application."""

from unittest.mock import Mock, patch

from starlette import status

from tests.conftest import ENPTestClient


def test_simple_route(client: ENPTestClient) -> None:
    """Test GET / to return Hello World.

    Args:
        client (ENPTestClient): Custom FastAPI client fixture

    """
    resp = client.get('/')
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == {'Hello': 'World'}


@patch('app.main.logger.info')
def test_simple_route_logs_hello_world(mock_logger: Mock, client: ENPTestClient) -> None:
    """Test that GET / logs 'Hello World' as an info log.

    Args:
        mock_logger (Mock): Mocked logger for capturing log calls.
        client (ENPTestClient): Custom FastAPI client fixture

    """
    client.get('/')

    # Check if the logger.info was called with "Hello World"
    mock_logger.assert_called_with('Hello World')
