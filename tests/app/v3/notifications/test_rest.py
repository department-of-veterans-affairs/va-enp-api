"""Test module for app/v3/notifications/rest.py."""

from uuid import UUID

from fastapi import status

from app.constants import RESPONSE_400
from app.v3.notifications.route_schema import NotificationSingleRequest
from tests.conftest import ENPTestClient


def test_get(client: ENPTestClient, uuid_factory: UUID) -> None:
    """Test GET /v3/notifications/.

    Args:
        client(ENPTestClient): Custom FastAPI client fixture
        uuid_factory (UUID): A parametrized UUID covering multiple UUID versions

    """
    resp = client.get(f'/v3/notifications/{uuid_factory}')
    assert resp.status_code == status.HTTP_200_OK


def test_get_missing_uuid(client: ENPTestClient) -> None:
    """Test GET /v3/notifications/ with a missing uuid.

    Args:
        client(ENPTestClient): Custom FastAPI client fixture

    """
    # will think it's supposed to be a POST so throws 405 instead of 404 (FastAPI)
    resp = client.get('/v3/notifications/')
    assert resp.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


def test_get_malformed_request(client: ENPTestClient) -> None:
    """Test GET /v3/notifications/ with a malformed request.

    Args:
        client(ENPTestClient): Custom FastAPI client fixture

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


def test_post(client: ENPTestClient, uuid_factory: UUID) -> None:
    """Test POST /v3/notifications/.

    Args:
        client(ENPTestClient): Custom FastAPI client fixture
        uuid_factory (UUID): A parametrized UUID covering multiple UUID versions

    """
    srequest = NotificationSingleRequest(
        to='vanotify@va.gov',
        personalization={'hello': 'world'},
        template=uuid_factory,
    )
    resp = client.post('v3/notifications', json=srequest.serialize())
    assert resp.status_code == status.HTTP_202_ACCEPTED


def test_post_no_personalization(client: ENPTestClient, uuid_factory: UUID) -> None:
    """Test POST /v3/notifications/ with no personalization.

    Args:
        client(ENPTestClient): Custom FastAPI client fixture
        uuid_factory (UUID): A parametrized UUID covering multiple UUID versions

    """
    srequest = NotificationSingleRequest(
        to='vanotify@va.gov',
        template=uuid_factory,
    )
    resp = client.post('v3/notifications', json=srequest.serialize())
    assert resp.status_code == status.HTTP_202_ACCEPTED


def test_post_malformed_request(client: ENPTestClient) -> None:
    """Test POST /v3/notifications/ with a malformed request.

    Args:
        client(ENPTestClient): Custom FastAPI client fixture

    """
    request: dict[str, str] = {}
    resp = client.post('v3/notifications', data=request)
    resp_text = resp.text

    # Response status code is correct
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    # Standard message is used
    assert RESPONSE_400 in resp_text
