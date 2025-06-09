"""Test file for routers."""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException, status
from fastapi.encoders import jsonable_encoder
from pydantic import UUID4, BaseModel

from app.constants import RESPONSE_500
from tests.conftest import ENPTestClient, router


class UuidRaise(BaseModel):
    """Model to test a response to faulty UUID4 input."""

    item: UUID4


@router.post('/uuid')
async def uuid_validation_fail(item: UuidRaise) -> None:
    """Route for a failed validation check to maintain backwards compatability with notification-api.

    Args:
        item (UuidRaise): Pydantic model that has a UUID4 field
    """
    ...


@router.get('/500')
def http_exception() -> None:
    """Route to raise an HTTPException.

    Raises:
        HTTPException: The exception raised
    """
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=RESPONSE_500)


@router.get('')
class TestLegacyTimedAPIRoute:
    """LegacyTimedAPIRoute test cases."""

    routes = (
        '/legacy/v2/notifications/sms',
        '/v2/notifications/sms',
    )

    async def test_http_exception_response(self, client: ENPTestClient) -> None:
        """Test route responds to HTTPExceptions as expected to maintain backwards compatability with notification-api.

        Args:
            client (ENPTestClient): Test client
        """
        response = client.get('/test/500')
        assert response.json() == {
            'errors': [{'error': 'BadRequestError', 'message': 'Server error'}],
            'status_code': 500,
        }

    async def test_uuid_version_response(self, client: ENPTestClient) -> None:
        """Test route with a bad UUID in the request to maintain backwards compatability with notification-api.

        Args:
            client (ENPTestClient): Test client
        """
        response = client.post('/test/uuid', json={'item': 'bad_uuid'})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            'errors': [{'error': 'ValidationError', 'message': 'item: Input should be a valid UUID version 4'}],
            'status_code': 400,
        }

    @pytest.mark.parametrize('route', routes)
    async def test_auth_error_uses_v2_json_structure(
        self,
        client: ENPTestClient,
        route: str,
        mocker: AsyncMock,
    ) -> None:
        """Test route response to an invalid authentication.

        Args:
            client (ENPTestClient): Test client
            route (str): Route to test
            mocker (AsyncMock): Mock object
        """
        # uses v2 routes because the bearer token responses need to match
        response = client.post(route, json={}, headers={'Authorization': ''})

        error_details = {
            'errors': [
                {
                    'error': 'AuthError',
                    'message': 'Unauthorized, authentication token must be provided',
                },
            ],
            'status_code': 401,
        }

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json() == error_details

    def test_uuid_raise(self, client: ENPTestClient) -> None:
        """Assert handler is tested.

        Args:
            client (ENPTestClient): Test client
        """
        client.post('/test/uuid', json=jsonable_encoder(UuidRaise(item=uuid4())))
