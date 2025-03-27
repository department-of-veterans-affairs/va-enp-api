"""Test suite for initializing FastAPI application."""

from asyncio import CancelledError
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from starlette import status

from app.main import CustomFastAPI, lifespan
from tests.conftest import ENPTestClient


def test_simple_route(client: ENPTestClient) -> None:
    """Test GET /enp to return Hello World.

    Args:
        client (ENPTestClient): Custom FastAPI client fixture

    """
    resp = client.get('/enp')
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == {'Hello': 'World'}
    assert 'X-Request-ID' in resp.headers


@patch('app.main.logger')
def test_simple_route_logs_hello_world(mock_logger: Mock, client: ENPTestClient) -> None:
    """Test that GET /enp logs 'Hello World' as an info log.

    Args:
        mock_logger (Mock): Mocked logger for capturing log calls.
        client (ENPTestClient): Custom FastAPI client fixture

    """
    client.get('/enp')
    mock_logger.info.assert_called_with('Hello World')


def test_specified_request_id_is_preserved(client: ENPTestClient) -> None:
    """Test that GET /enp headers propagate x-request-id from request to response.

    Args:
        client (ENPTestClient): Custom FastAPI client fixture

    """
    request_id = uuid4().hex
    response = client.get('/enp', headers={'X-Request-ID': request_id})
    # Ensure context data is available in the response
    assert 'X-Request-ID' in response.headers
    assert response.headers['X-Request-ID'] == request_id


async def test_lifespan_normal() -> None:
    """Test normal lifespan execution.

    Test that init_db() is called during stratup.
    Test that close_db() is called after normal context exit.

    """
    with (
        patch('app.main.init_db', new_callable=AsyncMock) as mock_init_db,
        patch('app.main.close_db', new_callable=AsyncMock) as mock_close_db,
    ):
        app = CustomFastAPI(lifespan=lifespan)

        async with lifespan(app):
            pass

        mock_init_db.assert_awaited_once()
        mock_close_db.assert_awaited_once()


async def test_lifespan_cancelled_exception() -> None:
    """Test lifespan execution when asyncio.CancelledError raised.

    Raises:
        CancelledError: Raised during shutdown, uvicorn ctrl-c

    Test that init_db() is called during stratup.
    Test that close_db() is called when asyncio.CancelledError raised in lifespan.

    """
    with (
        patch('app.main.init_db', new_callable=AsyncMock) as mock_init_db,
        patch('app.main.close_db', new_callable=AsyncMock) as mock_close_db,
    ):
        app = CustomFastAPI(lifespan=lifespan)

        # We expect an asyncio.CancelledError to be gracefully caught
        # Cannot test KeyboardInterrupt because it stops pytest. Hooks do not play nice with asyncio's CancelledError
        async with lifespan(app):
            raise CancelledError()

        mock_init_db.assert_awaited_once()
        mock_close_db.assert_awaited_once()
