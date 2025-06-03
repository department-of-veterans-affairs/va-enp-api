"""Test legacy auth."""

import time
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Type
from unittest.mock import patch
from uuid import uuid4

import jwt
import pytest
from fastapi import HTTPException, status
from sqlalchemy import Row
from starlette.datastructures import Headers
from starlette.requests import Request as StarletteRequest

from app.auth import (
    ACCESS_TOKEN_EXPIRE_SECONDS,
    ADMIN_CLIENT_USER_NAME,
    ADMIN_SECRET_KEY,
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
)
from app.constants import RESPONSE_LEGACY_INVALID_TOKEN_WRONG_TYPE
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


class TestJWTBearerAdmin:
    """Unit tests for the JWTBearerAdmin authentication dependency."""

    async def test_authenticates_valid_admin_token(self, admin_token_payload: JWTPayloadDict) -> None:
        """Verify JWTBearerAdmin authenticates a valid admin token."""
        token = generate_token(sig_key=ADMIN_SECRET_KEY, payload=admin_token_payload)

        headers = Headers({'authorization': f'Bearer {token}'})
        request = StarletteRequest(scope={'type': 'http', 'headers': headers.raw})
        auth = JWTBearerAdmin()

        await auth(request)

    async def test_raises_with_missing_bearer_header(self) -> None:
        """Test that JWTBearerAdmin raises HTTP 403 when Authorization header is missing."""
        headers = Headers()
        request = StarletteRequest(scope={'type': 'http', 'headers': headers.raw})
        auth = JWTBearerAdmin()

        with pytest.raises(HTTPException) as exc_info:
            await auth(request)

        exc = exc_info.value
        assert exc.status_code == status.HTTP_403_FORBIDDEN
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
        assert exc.status_code == status.HTTP_403_FORBIDDEN
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
        assert exc.status_code == status.HTTP_403_FORBIDDEN
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
        assert exc.status_code == status.HTTP_403_FORBIDDEN
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
        assert exc.status_code == status.HTTP_403_FORBIDDEN
        assert exc.detail == 'Invalid token: signature, api token is not valid'


class TestGetActiveServiceForIssuer:
    """Test suite for verifying behavior of the get_active_service_for_issuer function."""

    async def test_returns_service_row_for_valid_issuer(
        self,
        sample_service: Callable[..., Awaitable[Row[Any]]],
    ) -> None:
        """Should return service Row[Any] if issuer valid and service found."""
        service = await sample_service()

        with patch('app.auth.LegacyServiceDao.get_service', return_value=service):
            service_id, service_name = await get_active_service_for_issuer(str(service.id))

        # just checking if returned service id matches
        assert service_id == service.id
        assert service_name == service.name

    async def test_raises_with_invalid_issuer(self) -> None:
        """Should raise 403 with correct detail if the issuer invalid."""
        issuer = 'invalid-uuid'

        with pytest.raises(HTTPException) as exc_info:
            await get_active_service_for_issuer(issuer)

        exc = exc_info.value
        assert exc.status_code == status.HTTP_403_FORBIDDEN
        assert exc.detail == RESPONSE_LEGACY_INVALID_TOKEN_WRONG_TYPE

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

        with patch('app.auth.LegacyServiceDao.get_service', side_effect=raises):
            with pytest.raises(HTTPException) as exc_info:
                await get_active_service_for_issuer(issuer)

        exc = exc_info.value
        assert exc.status_code == status.HTTP_403_FORBIDDEN
        assert exc.detail == expected_detail

    async def test_raises_with_inactive_service(
        self,
        sample_service: Callable[..., Awaitable[Row[Any]]],
    ) -> None:
        """Should raise 403 if the service is archived (inactive)."""
        service = await sample_service(active=False)
        issuer = str(service.id)

        with patch('app.auth.LegacyServiceDao.get_service', return_value=service):
            with pytest.raises(HTTPException) as exc_info:
                await get_active_service_for_issuer(issuer)

        exc = exc_info.value
        assert exc.status_code == status.HTTP_403_FORBIDDEN
        assert exc.detail == 'Invalid token: service is archived'


class TestValidateServiceApiKey:
    """Test suite for validating service API key behavior and associated edge cases."""

    @pytest.fixture
    def sample_api_key_record(self) -> ApiKeyRecord:
        """Return valid sample api key record."""
        api_key = ApiKeyRecord(
            id=uuid4(),
            _secret_encrypted=encode_and_sign('not-so-secret'),
            service_id=uuid4(),
            expiry_date=datetime.now(timezone.utc) + timedelta(days=1),
            revoked=False,
            key_type='normal',
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
        assert exc.status_code == status.HTTP_403_FORBIDDEN
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
        assert exc.status_code == status.HTTP_403_FORBIDDEN
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
        assert exc.status_code == status.HTTP_403_FORBIDDEN
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
