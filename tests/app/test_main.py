"""Test suite for initializing FastAPI application."""

from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from starlette import status


def test_simple_route(client: TestClient) -> None:
    """Test GET / to return Hello World.

    Args:
    ----
        client (TestClient): FastAPI client fixture

    """
    resp = client.get('/')
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == {'Hello': 'World'}


@patch('app.main.app.logger.info')
def test_simple_route_logs_hello_world(mock_logger: Mock, client: TestClient) -> None:
    """Test that GET / logs 'Hello World' as an info log.

    Args:
    ----
        mock_logger (Mock): Mocked logger for capturing log calls.
        client (TestClient): FastAPI client fixture

    """
    client.get('/')

    # Check if the logger.info was called with "Hello World"
    mock_logger.assert_called_with('Hello World')
