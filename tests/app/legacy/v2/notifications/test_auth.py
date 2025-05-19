"""Test legacy auth."""

import base64
import time
from typing import Any, Awaitable, Callable
from unittest.mock import AsyncMock, Mock, patch

from fastapi import Request
from sqlalchemy import Row

from app.auth import JWTPayloadDict, verify_service_token
from tests.conftest import generate_token


async def test_verify_service_token(
    sample_api_key: Callable[..., Awaitable[Row[Any]]],
    sample_service: Callable[..., Awaitable[Row[Any]]],
) -> None:
    """Verify that a valid service token is accepted by verify_service_token.

    This test:
    - Creates a service and a matching API key
    - Mocks DAO methods to return these objects
    - Builds a JWT token signed with the API key secret
    - Asserts that verify_service_token accepts the token and populates the request state
    """
    # Create a sample service and API key
    service = await sample_service()
    secret = 'not_so_secret'
    encrypted_secret = f'{base64.b64encode(secret.encode()).decode()}.signature'
    api_key = await sample_api_key(service_id=service.id, secret=encrypted_secret)

    current_timestamp = int(time.time())
    payload: JWTPayloadDict = {
        'iss': str(service.id),
        'iat': current_timestamp + 120,
        'exp': current_timestamp + 180,
    }
    token = generate_token(sig_key='not_so_secret', payload=payload)

    # Create a mock FastAPI request with state
    request = Mock(spec=Request)
    request.state = Mock()

    with (
        patch('app.legacy.dao.services_dao.LegacyServiceDao.get_service', new=AsyncMock(return_value=service)),
        patch('app.legacy.dao.api_keys_dao.LegacyApiKeysDao.get_api_keys', new=AsyncMock(return_value=[api_key])),
    ):
        await verify_service_token(service_id=str(service.id), token=token, request=request)

    # Validate request state was set
    assert request.state.service_id == service.id
    assert request.state.authenticated_service == service
