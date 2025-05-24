"""Test legacy auth."""

import time
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Type, cast
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import jwt
import pytest
from fastapi import HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import Row
from starlette.datastructures import Headers
from starlette.requests import Request as StarletteRequest

from app.auth import (
    ACCESS_TOKEN_EXPIRE_SECONDS,
    ACCESS_TOKEN_LEEWAY_SECONDS,
    ADMIN_CLIENT_USER_NAME,
    ADMIN_SECRET_KEY,
    JWTBearer,
    JWTBearerAdmin,
    JWTPayloadDict,
    TokenAlgorithmError,
    TokenDecodeError,
    TokenExpiredError,
    TokenIssuedAtError,
    TokenIssuerError,
    _validate_service_api_key,
    get_active_service_for_issuer,
    get_token_issuer,
    validate_jwt_token,
    verify_service_token,
)
from app.exceptions import NonRetryableError, RetryableError
from app.legacy.dao.api_keys_dao import ApiKeyRecord
from tests.app.legacy.dao.test_api_keys import encode_and_sign
from tests.conftest import generate_token, generate_token_with_partial_payload


@pytest.fixture
def admin_token_payload() -> JWTPayloadDict:
    """Return valid admin JWT token payload."""
    current_timestamp = int(time.time())

    payload: JWTPayloadDict = {
        'iss': ADMIN_CLIENT_USER_NAME,
        'iat': current_timestamp,
        'exp': current_timestamp + ACCESS_TOKEN_EXPIRE_SECONDS,
    }
    return payload


@pytest.fixture
def service_token_payload() -> Callable[[str], JWTPayloadDict]:
    """Return valid admin JWT token payload."""

    def _service_token_payload(issuer: str) -> JWTPayloadDict:
        current_timestamp = int(time.time())

        payload: JWTPayloadDict = {
            'iss': issuer,
            'iat': current_timestamp,
            'exp': current_timestamp + ACCESS_TOKEN_EXPIRE_SECONDS,
        }
        return payload

    return _service_token_payload


class TestJWTBearerAdmin:
    """Unit tests for the JWTBearerAdmin authentication dependency."""

    async def test_authenticates_valid_admin_token(self, admin_token_payload: JWTPayloadDict) -> None:
        """Verify JWTBearerAdmin authenticates a valid admin token."""
        token = generate_token(sig_key=ADMIN_SECRET_KEY, payload=admin_token_payload)

        headers = Headers({'authorization': f'Bearer {token}'})
        request = StarletteRequest(scope={'type': 'http', 'headers': headers.raw})
        auth = JWTBearerAdmin()

        credentials = await auth(request)
        assert isinstance(credentials, HTTPAuthorizationCredentials)
        assert credentials.credentials == token

    async def test_raises_with_missing_bearer_header(self) -> None:
        """Test that JWTBearerAdmin raises HTTP 403 when Authorization header is missing."""
        headers = Headers()
        request = StarletteRequest(scope={'type': 'http', 'headers': headers.raw})
        auth = JWTBearerAdmin()

        with pytest.raises(HTTPException) as exc_info:
            await auth(request)

        exc = exc_info.value
        assert exc.status_code == 403
        assert exc.detail == 'Not authenticated'

    async def test_raises_with_invalid_token(self) -> None:
        """Test that JWTBearerAdmin raises HTTP 403 for an invalid token."""
        token = 'not-a-valid-token'

        headers = Headers({'authorization': f'Bearer {token}'})
        request = StarletteRequest(scope={'type': 'http', 'headers': headers.raw})
        auth = JWTBearerAdmin()

        with pytest.raises(HTTPException) as exc_info:
            await auth(request)

        exc = exc_info.value
        assert exc.status_code == 403
        assert exc.detail == 'Invalid token: signature, api token is not valid'

    async def test_raises_with_invalid_token_signature(self, admin_token_payload: JWTPayloadDict) -> None:
        """Test that JWTBearerAdmin raises HTTP 403 for a token with an invalid signature."""
        token = generate_token(sig_key='not-the-admin-secret', payload=admin_token_payload)

        headers = Headers({'authorization': f'Bearer {token}'})
        request = StarletteRequest(scope={'type': 'http', 'headers': headers.raw})
        auth = JWTBearerAdmin()

        with pytest.raises(HTTPException) as exc_info:
            await auth(request)

        exc = exc_info.value
        assert exc.status_code == 403
        assert exc.detail == 'Invalid token: signature, api token is not valid'

    async def test_raises_with_expired_token(self, admin_token_payload: JWTPayloadDict) -> None:
        """Test that JWTBearerAdmin raises HTTP 403 for an expired token."""
        payload = admin_token_payload
        current_timestamp = int(time.time())
        payload['exp'] = current_timestamp - ACCESS_TOKEN_EXPIRE_SECONDS
        token = generate_token(sig_key=ADMIN_SECRET_KEY, payload=payload)

        headers = Headers({'authorization': f'Bearer {token}'})
        request = StarletteRequest(scope={'type': 'http', 'headers': headers.raw})
        auth = JWTBearerAdmin()

        with pytest.raises(HTTPException) as exc_info:
            await auth(request)

        exc = exc_info.value
        assert exc.status_code == 403
        assert exc.detail == 'Invalid token: signature, api token is not valid'

    async def test_raises_with_invalid_algorithm(self, admin_token_payload: JWTPayloadDict) -> None:
        """Test that JWTBearerAdmin raises HTTP 403 for a token with an invalid algorithm."""
        jwt_headers = {
            'typ': 'JWT',
            'alg': 'HS384',
        }
        token = generate_token(sig_key=ADMIN_SECRET_KEY, headers=jwt_headers, payload=admin_token_payload)

        headers = Headers({'authorization': f'Bearer {token}'})
        request = StarletteRequest(scope={'type': 'http', 'headers': headers.raw})
        auth = JWTBearerAdmin()

        with pytest.raises(HTTPException) as exc_info:
            await auth(request)

        exc = exc_info.value
        assert exc.status_code == 403
        assert exc.detail == 'Invalid token: signature, api token is not valid'


class TestJWTBearer:
    """Unit tests for the JWTBearer authentication dependency."""

    async def test_authenticates_valid_admin_token(self, admin_token_payload: JWTPayloadDict) -> None:
        """Test that JWTBearer authenticates a valid admin token."""
        token = generate_token(sig_key=ADMIN_SECRET_KEY, payload=admin_token_payload)

        headers = Headers({'authorization': f'Bearer {token}'})
        request = StarletteRequest(scope={'type': 'http', 'headers': headers.raw})
        auth = JWTBearer()

        credentials = await auth(request)
        assert isinstance(credentials, HTTPAuthorizationCredentials)
        assert credentials.credentials == token

    async def test_authenticates_valid_service_token(
        self,
        sample_api_key: Callable[..., Awaitable[Row[Any]]],
        sample_service: Callable[..., Awaitable[Row[Any]]],
        service_token_payload: Callable[[str], JWTPayloadDict],
    ) -> None:
        """Test that JWTBearer authenticates a valid service token."""
        service = await sample_service()
        secret = 'not-so-secret'
        encrypted_secret = encode_and_sign(secret)
        api_key = await sample_api_key(service_id=service.id, secret=encrypted_secret)

        payload = service_token_payload(str(service.id))
        token = generate_token(sig_key=secret, payload=payload)

        headers = Headers({'authorization': f'Bearer {token}'})
        request = StarletteRequest(scope={'type': 'http', 'headers': headers.raw})
        auth = JWTBearer()

        with (
            patch('app.auth.LegacyServiceDao.get_service', new=AsyncMock(return_value=service)),
            patch('app.auth.LegacyApiKeysDao.get_api_keys', new=AsyncMock(return_value=[api_key])),
        ):
            credentials = await auth(request)

        assert isinstance(credentials, HTTPAuthorizationCredentials)
        assert credentials.credentials == token

    async def test_raises_with_missing_bearer_header(self) -> None:
        """Test that JWTBearer raises HTTP 403 when Authorization header is missing."""
        headers = Headers()
        request = StarletteRequest(scope={'type': 'http', 'headers': headers.raw})
        auth = JWTBearer()

        with pytest.raises(HTTPException) as exc_info:
            await auth(request)

        exc = exc_info.value
        assert exc.status_code == 403
        assert exc.detail == 'Not authenticated'

    async def test_raises_with_invalid_token(self) -> None:
        """Test that JWTBearer raises HTTP 403 for an invalid token."""
        headers = Headers({'authorization': f'Bearer {"not-a-valid-token"}'})
        request = StarletteRequest(scope={'type': 'http', 'headers': headers.raw})
        auth = JWTBearer()

        with pytest.raises(HTTPException) as exc_info:
            await auth(request)

        exc = exc_info.value
        assert exc.status_code == 403
        assert exc.detail == 'Invalid token: signature, api token is not valid'

    async def test_raises_with_admin_expired_token(self, admin_token_payload: JWTPayloadDict) -> None:
        """Test that JWTBearer raises HTTP 403 for an expired admin token."""
        payload = admin_token_payload
        current_timestamp = int(time.time())

        payload['exp'] = current_timestamp - ACCESS_TOKEN_EXPIRE_SECONDS
        token = generate_token(sig_key=ADMIN_SECRET_KEY, payload=payload)

        headers = Headers({'authorization': f'Bearer {token}'})
        request = StarletteRequest(scope={'type': 'http', 'headers': headers.raw})
        auth = JWTBearer()

        with pytest.raises(HTTPException) as exc_info:
            await auth(request)

        exc = exc_info.value
        assert exc.status_code == 403
        assert exc.detail == 'Invalid token: signature, api token is not valid'

    async def test_raises_with_invalid_algorithm(self, admin_token_payload: JWTPayloadDict) -> None:
        """Test that JWTBearer raises HTTP 403 for a token with an invalid algorithm."""
        jwt_headers = {
            'typ': 'JWT',
            'alg': 'HS384',
        }
        token = generate_token(sig_key=ADMIN_SECRET_KEY, headers=jwt_headers, payload=admin_token_payload)

        headers = Headers({'authorization': f'Bearer {token}'})
        request = StarletteRequest(scope={'type': 'http', 'headers': headers.raw})
        auth = JWTBearer()

        with pytest.raises(HTTPException) as exc_info:
            await auth(request)

        exc = exc_info.value
        assert exc.status_code == 403
        assert exc.detail == 'Invalid token: signature, api token is not valid'

    async def test_raises_with_missing_issuer(self, admin_token_payload: JWTPayloadDict) -> None:
        """Test that JWTBearer raises HTTP 403 when the issuer (iss) claim is missing."""
        raw_payload = dict(admin_token_payload)
        del raw_payload['iss']
        payload = cast(JWTPayloadDict, raw_payload)
        token = generate_token(sig_key=ADMIN_SECRET_KEY, payload=payload)

        headers = Headers({'authorization': f'Bearer {token}'})
        request = StarletteRequest(scope={'type': 'http', 'headers': headers.raw})
        auth = JWTBearer()

        with pytest.raises(HTTPException) as exc_info:
            await auth(request)

        exc = exc_info.value
        assert exc.status_code == 403
        assert exc.detail == 'Invalid token: iss field not provided'

    async def test_raises_with_service_not_found(
        self,
        service_token_payload: Callable[[str], JWTPayloadDict],
    ) -> None:
        """Test that JWTBearer raises HTTP 403 when the service referenced in the token is not found."""
        payload = service_token_payload(str(uuid4()))
        token = generate_token(sig_key='not-so-secret', payload=payload)

        headers = Headers({'authorization': f'Bearer {token}'})
        request = StarletteRequest(scope={'type': 'http', 'headers': headers.raw})
        auth = JWTBearer()

        with pytest.raises(HTTPException) as exc_info:
            await auth(request)

        exc = exc_info.value
        assert exc.status_code == 403
        assert exc.detail == 'Invalid token: service not found'

    async def test_raises_with_service_not_active(
        self,
        sample_service: Callable[..., Awaitable[Row[Any]]],
        service_token_payload: Callable[[str], JWTPayloadDict],
    ) -> None:
        """Test that JWTBearer raises HTTP 403 when the service is not active (archived)."""
        service = await sample_service(active=False)
        payload = service_token_payload(str(service.id))
        token = generate_token(sig_key='not-so-secret', payload=payload)

        headers = Headers({'authorization': f'Bearer {token}'})
        request = StarletteRequest(scope={'type': 'http', 'headers': headers.raw})
        auth = JWTBearer()

        with patch('app.auth.LegacyServiceDao.get_service', new=AsyncMock(return_value=service)):
            with pytest.raises(HTTPException) as exc_info:
                await auth(request)

        exc = exc_info.value
        assert exc.status_code == 403
        assert exc.detail == 'Invalid token: service is archived'

    @pytest.mark.parametrize(
        'raises',
        [
            NonRetryableError,
            RetryableError,
        ],
        ids=[
            'NonRetryableError from DAO',
            'RetryableError from DAO',
        ],
    )
    async def test_raises_with_any_api_key_dao_failure(
        self,
        sample_service: Callable[..., Awaitable[Row[Any]]],
        service_token_payload: Callable[[str], JWTPayloadDict],
        raises: Type[Exception],
    ) -> None:
        """Test that JWTBearer raises HTTP 403 when API key lookup fails with retryable or non-retryable error."""
        service = await sample_service()
        payload = service_token_payload(str(service.id))
        token = generate_token(sig_key='not-so-secret', payload=payload)

        headers = Headers({'authorization': f'Bearer {token}'})
        request = StarletteRequest(scope={'type': 'http', 'headers': headers.raw})
        auth = JWTBearer()

        with (
            patch('app.auth.LegacyServiceDao.get_service', new=AsyncMock(return_value=service)),
            patch('app.auth.LegacyApiKeysDao.get_api_keys', new=AsyncMock(side_effect=raises)),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await auth(request)

        exc = exc_info.value
        assert exc.status_code == 403
        assert exc.detail == 'Invalid token: service has no API keys'

    async def test_raises_with_no_api_keys_for_service(
        self,
        sample_service: Callable[..., Awaitable[Row[Any]]],
        service_token_payload: Callable[[str], JWTPayloadDict],
    ) -> None:
        """Test that JWTBearer raises HTTP 403 when the service has no associated API keys."""
        service = await sample_service()
        payload = service_token_payload(str(service.id))
        token = generate_token(sig_key='not-so-secret', payload=payload)

        headers = Headers({'authorization': f'Bearer {token}'})
        request = StarletteRequest(scope={'type': 'http', 'headers': headers.raw})
        auth = JWTBearer()

        with (
            patch('app.auth.LegacyServiceDao.get_service', new=AsyncMock(return_value=service)),
            patch('app.auth.LegacyApiKeysDao.get_api_keys', new=AsyncMock(return_value=[])),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await auth(request)

        exc = exc_info.value
        assert exc.status_code == 403
        assert exc.detail == 'Invalid token: service has no API keys'

    @pytest.mark.parametrize(
        'encrypted_secret',
        [
            None,
            encode_and_sign('not-so-secret'),
        ],
        ids=[
            'API key has no secret (None)',
            'API key has a different secret than provided service token',
        ],
    )
    async def test_raises_with_no_matching_secrets(
        self,
        sample_api_key: Callable[..., Awaitable[Row[Any]]],
        sample_service: Callable[..., Awaitable[Row[Any]]],
        service_token_payload: Callable[[str], JWTPayloadDict],
        encrypted_secret: str | None,
    ) -> None:
        """Test that JWTBearer raises HTTP 403 when no API key secret matches the token signature."""
        service = await sample_service()
        api_key = await sample_api_key(service_id=service.id, secret=encrypted_secret)

        payload = service_token_payload(str(service.id))
        token = generate_token(sig_key='not-the-matching-secret', payload=payload)

        headers = Headers({'authorization': f'Bearer {token}'})
        request = StarletteRequest(scope={'type': 'http', 'headers': headers.raw})
        auth = JWTBearer()

        with (
            patch('app.auth.LegacyServiceDao.get_service', new=AsyncMock(return_value=service)),
            patch('app.auth.LegacyApiKeysDao.get_api_keys', new=AsyncMock(return_value=[api_key])),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await auth(request)

        exc = exc_info.value
        assert exc.status_code == 403
        assert exc.detail == 'Invalid token: signature, api token not found'

    async def test_raises_with_service_expired_token(
        self,
        sample_api_key: Callable[..., Awaitable[Row[Any]]],
        sample_service: Callable[..., Awaitable[Row[Any]]],
        service_token_payload: Callable[[str], JWTPayloadDict],
    ) -> None:
        """Test that JWTBearer raises HTTP 403 when the service token is expired."""
        service = await sample_service()
        secret = 'not-so-secret'
        encrypted_secret = encode_and_sign(secret)
        api_key = await sample_api_key(service_id=service.id, secret=encrypted_secret)

        payload = service_token_payload(str(service.id))
        current_timestamp = int(time.time())
        payload['exp'] = current_timestamp - ACCESS_TOKEN_EXPIRE_SECONDS
        token = generate_token(sig_key=secret, payload=payload)

        headers = Headers({'authorization': f'Bearer {token}'})
        request = StarletteRequest(scope={'type': 'http', 'headers': headers.raw})
        auth = JWTBearer()

        with (
            patch('app.auth.LegacyServiceDao.get_service', new=AsyncMock(return_value=service)),
            patch('app.auth.LegacyApiKeysDao.get_api_keys', new=AsyncMock(return_value=[api_key])),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await auth(request)

        exc = exc_info.value
        assert exc.status_code == 403
        assert exc.detail == 'Error: Your system clock must be accurate to within 30 seconds'

    async def test_raises_with_invalid_algorithm_service_token(
        self,
        sample_api_key: Callable[..., Awaitable[Row[Any]]],
        sample_service: Callable[..., Awaitable[Row[Any]]],
        service_token_payload: Callable[[str], JWTPayloadDict],
    ) -> None:
        """Test that JWTBearer raises HTTP 403 for a service token with an invalid algorithm."""
        service = await sample_service()
        secret = 'not-so-secret'
        encrypted_secret = encode_and_sign(secret)
        api_key = await sample_api_key(service_id=service.id, secret=encrypted_secret)

        payload = service_token_payload(str(service.id))
        jwt_headers = {
            'typ': 'JWT',
            'alg': 'HS384',
        }
        token = generate_token(sig_key=secret, headers=jwt_headers, payload=payload)

        headers = Headers({'authorization': f'Bearer {token}'})
        request = StarletteRequest(scope={'type': 'http', 'headers': headers.raw})
        auth = JWTBearer()

        with (
            patch('app.auth.LegacyServiceDao.get_service', new=AsyncMock(return_value=service)),
            patch('app.auth.LegacyApiKeysDao.get_api_keys', new=AsyncMock(return_value=[api_key])),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await auth(request)

        exc = exc_info.value
        assert exc.status_code == 403
        assert exc.detail == 'Invalid token: signature, api token not found'

    async def test_raises_with_missing_issued_at(
        self,
        sample_api_key: Callable[..., Awaitable[Row[Any]]],
        sample_service: Callable[..., Awaitable[Row[Any]]],
        service_token_payload: Callable[[str], JWTPayloadDict],
    ) -> None:
        """Test that JWTBearer raises HTTP 403 when the issued-at (iat) claim is missing from the service token."""
        service = await sample_service()
        secret = 'not-so-secret'
        encrypted_secret = encode_and_sign(secret)
        api_key = await sample_api_key(service_id=service.id, secret=encrypted_secret)

        raw_payload = dict(service_token_payload(str(service.id)))
        del raw_payload['iat']
        # casting a raw dictionary to JWTPayloadDict to keep mypy happy
        payload = cast(JWTPayloadDict, raw_payload)
        token = generate_token(sig_key=secret, payload=payload)

        headers = Headers({'authorization': f'Bearer {token}'})
        request = StarletteRequest(scope={'type': 'http', 'headers': headers.raw})
        auth = JWTBearer()

        with (
            patch('app.auth.LegacyServiceDao.get_service', new=AsyncMock(return_value=service)),
            patch('app.auth.LegacyApiKeysDao.get_api_keys', new=AsyncMock(return_value=[api_key])),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await auth(request)

        exc = exc_info.value
        assert exc.status_code == 403
        assert exc.detail == 'Invalid token: signature, api token not found'

    @pytest.mark.parametrize(
        'issued_at_offset_seconds',
        [
            -ACCESS_TOKEN_EXPIRE_SECONDS - ACCESS_TOKEN_LEEWAY_SECONDS,
            ACCESS_TOKEN_EXPIRE_SECONDS + ACCESS_TOKEN_LEEWAY_SECONDS,
        ],
        ids=[
            'JWT iat field (issued_at) is offset too far into the past',
            'JWT iat field (issued_at) is offset into the future',
        ],
    )
    async def test_raises_with_invalid_issued_at(
        self,
        sample_api_key: Callable[..., Awaitable[Row[Any]]],
        sample_service: Callable[..., Awaitable[Row[Any]]],
        service_token_payload: Callable[[str], JWTPayloadDict],
        issued_at_offset_seconds: int,
    ) -> None:
        """Test that JWTBearer raises HTTP 403 when the issued-at (iat) claim is outside the allowed time window."""
        service = await sample_service()
        secret = 'not-so-secret'
        encrypted_secret = encode_and_sign(secret)
        api_key = await sample_api_key(service_id=service.id, secret=encrypted_secret)

        payload = service_token_payload(str(service.id))
        payload['iat'] += issued_at_offset_seconds
        token = generate_token(sig_key=secret, payload=payload)

        headers = Headers({'authorization': f'Bearer {token}'})
        request = StarletteRequest(scope={'type': 'http', 'headers': headers.raw})
        auth = JWTBearer()

        with (
            patch('app.auth.LegacyServiceDao.get_service', new=AsyncMock(return_value=service)),
            patch('app.auth.LegacyApiKeysDao.get_api_keys', new=AsyncMock(return_value=[api_key])),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await auth(request)

        exc = exc_info.value
        assert exc.status_code == 403
        assert exc.detail == 'Error: Your system clock must be accurate to within 30 seconds'

    async def test_raises_with_api_key_revoked(
        self,
        sample_api_key: Callable[..., Awaitable[Row[Any]]],
        sample_service: Callable[..., Awaitable[Row[Any]]],
        service_token_payload: Callable[[str], JWTPayloadDict],
    ) -> None:
        """Test that JWTBearer raises HTTP 403 when the API key used in the token is revoked."""
        service = await sample_service()
        secret = 'not-so-secret'
        encrypted_secret = encode_and_sign(secret)
        api_key = await sample_api_key(service_id=service.id, secret=encrypted_secret, revoked=True)

        payload = service_token_payload(str(service.id))
        token = generate_token(sig_key=secret, payload=payload)

        headers = Headers({'authorization': f'Bearer {token}'})
        request = StarletteRequest(scope={'type': 'http', 'headers': headers.raw})
        auth = JWTBearer()

        with (
            patch('app.auth.LegacyServiceDao.get_service', new=AsyncMock(return_value=service)),
            patch('app.auth.LegacyApiKeysDao.get_api_keys', new=AsyncMock(return_value=[api_key])),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await auth(request)

        exc = exc_info.value
        assert exc.status_code == 403
        assert exc.detail == 'Invalid token: API key revoked'


class TestVerifyServiceToken:
    """Test suite for verifying behavior of the verify_service_token function."""

    async def test_authenticates_valid_service_token_and_sets_request_state_service_id(
        self,
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
        encrypted_secret = encode_and_sign(secret)
        api_key = await sample_api_key(service_id=service.id, secret=encrypted_secret)

        current_timestamp = int(time.time())
        payload: JWTPayloadDict = {
            'iss': str(service.id),
            'iat': current_timestamp,
            'exp': current_timestamp + ACCESS_TOKEN_EXPIRE_SECONDS,
        }
        token = generate_token(sig_key='not_so_secret', payload=payload)

        # Create a mock FastAPI request with state
        request = Mock(spec=Request)
        request.state = Mock()

        with (
            patch('app.auth.LegacyServiceDao.get_service', new=AsyncMock(return_value=service)),
            patch('app.auth.LegacyApiKeysDao.get_api_keys', new=AsyncMock(return_value=[api_key])),
        ):
            await verify_service_token(issuer=payload['iss'], token=token, request=request)

        # Validate request state was set
        assert request.state.service_id == service.id


class TestGetActiveServiceForIssuer:
    """Test suite for verifying behavior of the get_active_service_for_issuer function."""

    async def test_returns_service_row_for_valid_issuer(
        self,
        sample_service: Callable[..., Awaitable[Row[Any]]],
    ) -> None:
        """Should return service Row[Any] if issuer valid and service found."""
        service = await sample_service()
        request_id = uuid4()

        with patch('app.auth.LegacyServiceDao.get_service', new=AsyncMock(return_value=service)):
            service_by_issuer = await get_active_service_for_issuer(str(service.id), request_id)

        # just checking if returned service id matches
        assert service_by_issuer.id == service.id

    async def test_raises_with_invalid_issuer(self) -> None:
        """Should raise 403 with correct detail if the issuer invalid."""
        issuer = 'invalid-uuid'
        request_id = uuid4()

        with pytest.raises(HTTPException) as exc_info:
            await get_active_service_for_issuer(issuer, request_id)

        exc = exc_info.value
        assert exc.status_code == 403
        assert exc.detail == 'Invalid token: service id is not the right data type'

    @pytest.mark.parametrize(
        ('raises', 'expected_detail'),
        [
            (NonRetryableError, 'Invalid token: service not found'),
            (RetryableError, 'Invalid token: service not found'),
        ],
    )
    async def test_raises_on_any_service_DAO_error(
        self,
        raises: Type[Exception],
        expected_detail: str,
    ) -> None:
        """Should raise 403 with correct detail if the service ID is invalid or not found."""
        issuer = str(uuid4())
        request_id = uuid4()

        with patch('app.auth.LegacyServiceDao.get_service', side_effect=raises):
            with pytest.raises(HTTPException) as exc_info:
                await get_active_service_for_issuer(issuer, request_id)

        exc = exc_info.value
        assert exc.status_code == 403
        assert exc.detail == expected_detail

    async def test_raises_with_inactive_service(
        self,
        sample_service: Callable[..., Awaitable[Row[Any]]],
    ) -> None:
        """Should raise 403 if the service is archived (inactive)."""
        service = await sample_service(active=False)
        issuer = str(service.id)
        request_id = uuid4()

        with patch('app.auth.LegacyServiceDao.get_service', new=AsyncMock(return_value=service)):
            with pytest.raises(HTTPException) as exc_info:
                await get_active_service_for_issuer(issuer, request_id)

        exc = exc_info.value
        assert exc.status_code == 403
        assert exc.detail == 'Invalid token: service is archived'


class TestValidateServiceApiKey:
    """Test suite for validating service API key behavior and associated edge cases."""

    @pytest.fixture
    def sample_api_key_record(self) -> ApiKeyRecord:
        """Return valid sample api key record."""
        api_key = ApiKeyRecord(
            id=uuid4(),
            _secret_encrypted=None,
            service_id=uuid4(),
            expiry_date=datetime.now(timezone.utc) + timedelta(days=1),
            revoked=False,
        )
        return api_key

    def test_validates_api_key(self, sample_api_key_record: ApiKeyRecord) -> None:
        """Should not raise exception or log warnings."""
        service_name = 'sample service'
        api_key = sample_api_key_record
        with patch('app.auth.logger.warning') as mock_warning:
            _validate_service_api_key(api_key, str(api_key.service_id), service_name)

        mock_warning.assert_not_called()

    def test_raises_with_revoked_key(self, sample_api_key_record: ApiKeyRecord) -> None:
        """Should raise 403 if the API key is revoked."""
        service_name = 'sample service'
        api_key = sample_api_key_record
        api_key.revoked = True
        with pytest.raises(HTTPException) as exc_info:
            _validate_service_api_key(api_key, str(api_key.service_id), service_name)

        exc = exc_info.value
        assert exc.status_code == 403
        assert exc.detail == 'Invalid token: API key revoked'

    def test_logs_warning_with_no_expiry(self, sample_api_key_record: ApiKeyRecord) -> None:
        """Should log a warning if the API key has no expiry date."""
        service_name = 'sample service'
        api_key = sample_api_key_record
        api_key.expiry_date = None

        with patch('app.auth.logger.warning') as mock_warning:
            _validate_service_api_key(api_key, str(api_key.service_id), service_name)

            mock_warning.assert_called_once_with(
                'service {} - {} used old-style api key {} with no expiry_date',
                str(api_key.service_id),
                service_name,
                api_key.id,
            )

    def test_logs_warning_with_expired_key(self, sample_api_key_record: ApiKeyRecord) -> None:
        """Should log a warning if the API key is expired."""
        service_name = 'sample service'
        api_key = sample_api_key_record
        api_key.expiry_date = datetime.now(timezone.utc) - timedelta(days=1)

        with patch('app.auth.logger.warning') as mock_warning:
            _validate_service_api_key(api_key, str(api_key.service_id), service_name)

            mock_warning.assert_called_once_with(
                'service {} - {} used expired api key {} expired as of {}',
                str(api_key.service_id),
                service_name,
                api_key.id,
                api_key.expiry_date,
            )


class TestGetTokenIssuer:
    """Test suite for verifying behavior of get_token_issuer function with various token conditions."""

    def test_returns_issuer_for_decodable_token(self) -> None:
        """Test that get_token_issuer returns the correct issuer from a valid token."""
        current_timestamp = int(time.time())
        issuer = str(uuid4())
        payload: JWTPayloadDict = {
            'iss': issuer,
            'iat': current_timestamp,
            'exp': current_timestamp + ACCESS_TOKEN_EXPIRE_SECONDS,
        }

        headers = {
            'typ': 'JWT',
            'alg': 'HS256',
        }

        token = jwt.encode(dict(payload), 'not_so_secret', headers=headers)

        assert get_token_issuer(token) == issuer, 'extracted issuer should match token issuer'

    def test_raises_with_invalid_token(self) -> None:
        """Should raise HTTP 403 if the token cannot be decoded."""
        with pytest.raises(HTTPException) as exc_info:
            get_token_issuer('not a valid token')

        exc = exc_info.value
        assert exc.status_code == 403
        assert exc.detail == 'Invalid token: signature, api token is not valid'

    def test_raises_with_missing_issuer(self) -> None:
        """Should raise TokenIssuerError if the token is missing the 'iss' claim."""
        current_timestamp = int(time.time())
        partial_payload = {
            'iat': current_timestamp,
            'exp': current_timestamp + 60,
        }
        token = generate_token_with_partial_payload(sig_key='not_so_secret', payload=partial_payload)
        with pytest.raises(HTTPException) as exc_info:
            get_token_issuer(token)

        exc = exc_info.value
        assert exc.status_code == 403
        assert exc.detail == 'Invalid token: iss field not provided'


class TestValidateJwtToken:
    """Test suite for validating JWT token claims and expiration handling."""

    def test_validates_token(self) -> None:
        """Should return True for valid token."""
        current_timestamp = int(time.time())
        payload = {
            'iss': str(uuid4()),
            'iat': current_timestamp,
            'exp': current_timestamp + ACCESS_TOKEN_EXPIRE_SECONDS,
        }
        assert validate_jwt_token(payload)

    def test_raises_with_missing_issuer(self) -> None:
        """Should raise TokenIssuerError if the token is missing the 'iss' claim."""
        current_timestamp = int(time.time())
        payload = {
            'iat': current_timestamp,
            'exp': current_timestamp,
        }
        with pytest.raises(TokenIssuerError):
            validate_jwt_token(payload)

    def test_raises_with_missing_issued_at(self) -> None:
        """Should raise TokenIssuedAtError if the token is missing the 'iat' claim."""
        current_timestamp = int(time.time())
        partial_payload = {
            'iss': 'sample service',
            'exp': current_timestamp + ACCESS_TOKEN_EXPIRE_SECONDS,
        }
        with pytest.raises(TokenIssuedAtError):
            validate_jwt_token(partial_payload)

    def test_raises_with_expired_token(self) -> None:
        """Should raise TokenExpiredError if the token is expired."""
        current_timestamp = int(time.time())
        partial_payload = {
            'iss': 'sample service',
            'iat': current_timestamp - ACCESS_TOKEN_EXPIRE_SECONDS - 1,
        }
        with pytest.raises(TokenExpiredError):
            validate_jwt_token(partial_payload)

    def test_raises_with_future_token(self) -> None:
        """Should raise TokenExpiredError if the token is issued too far in the future."""
        current_timestamp = int(time.time())
        partial_payload = {
            'iss': 'sample service',
            'iat': current_timestamp + (2 * ACCESS_TOKEN_EXPIRE_SECONDS),
        }
        with pytest.raises(TokenExpiredError):
            validate_jwt_token(partial_payload)


class TestTokenErrors:
    """Test suite for verifying instantiation and behavior of custom token-related exceptions."""

    def test_token_expired_error_instantiation(self) -> None:
        """Should instantiate TokenExpiredError with message and token."""
        minimal_token = {
            'iss': 'sample service',
            'iat': 0,
        }
        err = TokenExpiredError('token expired', token=minimal_token)
        assert isinstance(err, TokenExpiredError)
        assert err.message == 'token expired'
        assert err.token == minimal_token

    def test_token_algorithm_error_instantiation(self) -> None:
        """Should instantiate TokenAlgorithmError with the correct message."""
        err = TokenAlgorithmError()
        assert isinstance(err, TokenAlgorithmError)
        assert 'algorithm used is not' in err.message

    def test_token_decode_error_with_message(self) -> None:
        """Should instantiate TokenDecodeError with a custom message."""
        err = TokenDecodeError('bad signature')
        assert isinstance(err, TokenDecodeError)
        assert err.message == 'bad signature'

    def test_token_decode_error_without_message(self) -> None:
        """Should instantiate TokenDecodeError with the default message."""
        err = TokenDecodeError()
        assert err.message == 'Invalid token: signature'

    def test_token_issuer_error_instantiation(self) -> None:
        """Should instantiate TokenIssuerError with the correct message."""
        err = TokenIssuerError()
        assert isinstance(err, TokenIssuerError)
        assert err.message == 'Invalid token: iss field not provided'

    def test_token_issued_at_error_instantiation(self) -> None:
        """Should instantiate TokenIssuedAtError with the correct message."""
        err = TokenIssuedAtError()
        assert isinstance(err, TokenIssuedAtError)
        assert err.message == 'Invalid token: iat field not provided'
