"""Test module for app/v3/notifications/rest.py."""

from unittest.mock import Mock, patch
from uuid import uuid4

from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from app.v3.notifications.rest import RESPONSE_400
from app.v3.notifications.route_schema import NotificationSingleRequest


def test_get(client: TestClient) -> None:
    """Test GET /v3/notifications/.

    Args:
    ----
        client(TestClient): FastAPI client fixture

    """
    resp = client.get(f'/v3/notifications/{uuid4()}')
    assert resp.status_code == status.HTTP_200_OK


def test_get_missing_uuid(client: TestClient) -> None:
    """Test GET /v3/notifications/ with a missing uuid.

    Args:
    ----
        client(TestClient): FastAPI client fixture

    """
    # will think it's supposed to be a POST so throws 405 instead of 404 (FastAPI)
    resp = client.get('/v3/notifications/')
    assert resp.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


def test_get_malformed_request(client: TestClient) -> None:
    """Test GET /v3/notifications/ with a malformed request.

    Args:
    ----
        client(TestClient): FastAPI client fixture

    """
    malformed_uuid = '1234'
    resp = client.get(f'/v3/notifications/{malformed_uuid}')
    resp_text = resp.text

    # Response status code is correct
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    # Standard message is used
    assert RESPONSE_400 in resp_text
    # The thing that was invalid is in the response
    assert malformed_uuid in resp_text


def test_post(client: TestClient) -> None:
    """Test POST /v3/notifications/.

    Args:
    ----
        client(TestClient): FastAPI client fixture

    """
    srequest = NotificationSingleRequest(
        to='vanotify@va.gov',
        personalization={'hello': 'world'},
        template=uuid4(),
    )
    resp = client.post('v3/notifications', json=srequest.serialize())
    assert resp.status_code == status.HTTP_202_ACCEPTED


def test_post_no_personalization(client: TestClient) -> None:
    """Test POST /v3/notifications/ with no personalization.

    Args:
    ----
        client(TestClient): FastAPI client fixture

    """
    srequest = NotificationSingleRequest(
        to='vanotify@va.gov',
        template=uuid4(),
    )
    resp = client.post('v3/notifications', json=srequest.serialize())
    assert resp.status_code == status.HTTP_202_ACCEPTED


def test_post_malformed_request(client: TestClient) -> None:
    """Test POST /v3/notifications/ with a malformed request.

    Args:
    ----
        client(TestClient): FastAPI client fixture

    """
    request: dict[str, str] = {}
    resp = client.post('v3/notifications', data=request)
    resp_text = resp.text

    # Response status code is correct
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    # Standard message is used
    assert RESPONSE_400 in resp_text


def test_post_returns_200(client: TestClient) -> None:
    """Test POST /v3/notifications/not-implemented with no personalization.

    Args:
    ----
        client(TestClient): FastAPI client fixture

    """
    resp = client.post('v3/notifications/not-implemented')

    assert resp.status_code == status.HTTP_200_OK


@patch('app.v3.notifications.rest.test_cov_helper', side_effect=NotImplementedError)
def test_post_returns_500(test_cov_helper: Mock, client: TestClient) -> None:
    """Test POST /v3/notifications/not-implemented with no personalization.

    Args:
    ----
        test_cov_helper (Mock): Mocked function that raises a NotImplementedError
        client (TestClient): FastAPI client fixture

    """
    resp = client.post('v3/notifications/not-implemented')

    assert resp.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


@patch(
    'app.v3.notifications.rest.test_cov_helper',
    side_effect=HTTPException(status.HTTP_404_NOT_FOUND, detail='Item not found'),
)
def test_post_returns_404(test_cov_helper: Mock, client: TestClient) -> None:
    """Test POST /v3/notifications/not-implemented with no personalization.

    Args:
    ----
        test_cov_helper (Mock): Mocked function that raises an HTTPException
        client (TestClient): FastAPI client fixture

    """
    resp = client.post('v3/notifications/not-implemented')

    assert resp.status_code == status.HTTP_404_NOT_FOUND
