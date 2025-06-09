"""Tests for the authentication module."""

import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import jwt
import pytest
from fastapi import HTTPException, Request, status
from fastapi.security import HTTPBearer

from app.auth import (
    ADMIN_SECRET_KEY,
    ALGORITHM,
    JWTBearer,
    JWTBearerAdmin,
    JWTPayloadDict,
    TokenAlgorithmError,
    TokenDecodeError,
    TokenExpiredError,
    TokenIssuedAtError,
    TokenIssuerError,
    _get_service_api_keys,
    _get_token_issuer,
    _validate_service_api_key,
    _verify_service_token,
    decode_jwt_token,
    decode_token,
    get_active_service_for_issuer,
    get_token_issuer,
    validate_jwt_token,
    verify_admin_token,
    verify_service_token,
)
from app.constants import (
    RESPONSE_403,
    RESPONSE_LEGACY_ERROR_SYSTEM_CLOCK,
    RESPONSE_LEGACY_INVALID_TOKEN_ARCHIVED_SERVICE,
    RESPONSE_LEGACY_INVALID_TOKEN_NO_ISS,
    RESPONSE_LEGACY_INVALID_TOKEN_NO_KEYS,
    RESPONSE_LEGACY_INVALID_TOKEN_NO_SERVICE,
    RESPONSE_LEGACY_INVALID_TOKEN_NOT_FOUND,
    RESPONSE_LEGACY_INVALID_TOKEN_NOT_VALID,
    RESPONSE_LEGACY_INVALID_TOKEN_REVOKED,
    RESPONSE_LEGACY_INVALID_TOKEN_WRONG_TYPE,
    RESPONSE_LEGACY_NO_CREDENTIALS,
)
from app.exceptions import NonRetryableError, RetryableError
from app.legacy.dao.api_keys_dao import ApiKeyRecord
from tests.app.legacy.dao.test_api_keys import encode_and_sign


@patch('app.auth.context')
class TestVerifyServiceToken:
    """Test suite for verifying behavior of the verify_service_token function."""

    async def test_mocked_happy_path(
        self,
        mock_context: AsyncMock,
        mocker: AsyncMock,
    ) -> None:
        """Test happy path.

        Args:
            mock_context (AsyncMock): Mocked starlette context
            mocker (AsyncMock): Mock object
        """
        # new_callable=AsyncMock to avoid the cache
        mock_service = mocker.patch(
            'app.auth.get_active_service_for_issuer', new_callable=AsyncMock, return_value=(uuid4(), 'service_name')
        )
        mock_service.id = uuid4()
        mock_service.name = 'Mock Name'
        mock_api_key = mocker.patch.object(ApiKeyRecord, 'from_row')
        mocker.patch('app.auth._get_service_api_keys', new_callable=AsyncMock, return_value=[mock_api_key])
        mocker.patch('app.auth._verify_service_token', return_value=True)
        mocker.patch('app.auth._validate_service_api_key')

        await verify_service_token(str(mock_service.id), 'Fake token')

    @pytest.mark.parametrize('token', ['', '12345', '💬', '短信'], ids=['empty', 'number', 'emoji', 'sms-character'])
    async def test_token_error_exception(
        self,
        mock_context: AsyncMock,
        token: str,
    ) -> None:
        """Test token fail is compatible with notification-api.

        Args:
            mock_context (AsyncMock): Mocked starlette context
            token (str): A token value
        """
        with pytest.raises(HTTPException) as exc_info:
            await verify_service_token(str(uuid4()), token)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert exc_info.value.detail == RESPONSE_LEGACY_INVALID_TOKEN_NO_SERVICE

    async def test_no_valid_api_keys(
        self,
        mock_context: AsyncMock,
        mocker: AsyncMock,
    ) -> None:
        """Test no valid api keys fail is compatible with notification-api.

        Args:
            mock_context (AsyncMock): Mocked starlette context
            mocker (AsyncMock): Mock object
        """
        # new_callable=AsyncMock to avoid the cache
        mock_service = mocker.patch(
            'app.auth.get_active_service_for_issuer', new_callable=AsyncMock, return_value=(uuid4(), str(uuid4()))
        )
        mock_api_key = mocker.patch.object(ApiKeyRecord, 'from_row')
        mocker.patch('app.auth._get_service_api_keys', new_callable=AsyncMock, return_value=[mock_api_key])

        with pytest.raises(HTTPException) as exc_info:
            await verify_service_token(str(mock_service.id), 'Fake token')
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert exc_info.value.detail == RESPONSE_LEGACY_INVALID_TOKEN_NOT_FOUND


class TestVerifyAdminToken:
    """Test verify_admin_token method."""

    def test_happy_path(self) -> None:
        """Test happy path."""
        token = jwt.encode({}, ADMIN_SECRET_KEY, headers={'typ': 'JWT', 'alg': ALGORITHM})
        assert verify_admin_token(token) is True

    @pytest.mark.parametrize('test_exception', [jwt.PyJWTError, jwt.ImmatureSignatureError])
    def test_decode_error(self, test_exception: Exception, mocker: AsyncMock) -> None:
        """Test decode error does not validate admin auth.

        Args:
            test_exception (Exception): Exception to raise
            mocker (AsyncMock): Mock object
        """
        mocker.patch('app.auth.jwt.decode', side_effect=test_exception)
        assert verify_admin_token('Fake token') is False


class TestGetServiceApiKeys:
    """Test _get_service_api_keys method."""

    async def test_happy_path(self, mocker: AsyncMock) -> None:
        """Test happy path.

        This test verifies that _get_service_api_keys does not raise an HTTPException
        when the DAO returns at least one API key. The actual contents of the
        returned API keys are not validated—only the absence of an exception is asserted.

        Args:
            mocker (AsyncMock): Mock object
        """
        mock_dao = mocker.patch('app.auth.LegacyApiKeysDao.get_service_api_keys', new_callable=AsyncMock)
        mock_dao.return_value = [mocker.Mock()]

        # Should not raise HTTPException
        await _get_service_api_keys(uuid4())

    async def test_no_api_keys(self, mocker: AsyncMock) -> None:
        """Test happy path.

        Args:
            mocker (AsyncMock): Mock object
        """
        mocker.patch('app.auth.LegacyApiKeysDao.get_service_api_keys', new_callable=AsyncMock)
        with pytest.raises(HTTPException) as exc_info:
            await _get_service_api_keys(uuid4())
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert exc_info.value.detail == RESPONSE_LEGACY_INVALID_TOKEN_NO_KEYS

    @pytest.mark.parametrize('test_exception', [RetryableError, NonRetryableError])
    async def test_dao_errors(self, test_exception: Exception, mocker: AsyncMock) -> None:
        """Test dao failures are compatible with notification-api.

        Notification-API uses a combined service and API lookup and return service not found for dao errors.
        Returning service has no API keys is the closest matching error message in this case.

        Args:
            test_exception (Exception): Exception to raise
            mocker (AsyncMock): Mock object
        """
        mocker.patch('app.auth.LegacyApiKeysDao.get_service_api_keys', side_effect=test_exception)
        with pytest.raises(HTTPException) as exc_info:
            await _get_service_api_keys(uuid4())
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert exc_info.value.detail == RESPONSE_LEGACY_INVALID_TOKEN_NO_KEYS


class TestInternalVerifyServiceToken:
    """Test _verify_service_token method."""

    async def test_happy_path(self, mocker: AsyncMock) -> None:
        """Test happy path.

        Args:
            mocker (AsyncMock): Mock object
        """
        mocker.patch('app.auth.decode_jwt_token', return_value=True)
        assert _verify_service_token('Fake token', mocker.Mock()) is True

    async def test_not_verified(self, mocker: AsyncMock) -> None:
        """Test not verified.

        Args:
            mocker (AsyncMock): Mock object
        """
        assert _verify_service_token('Fake token', mocker.Mock()) is False

    async def test_clock_error(self, mocker: AsyncMock) -> None:
        """Test clock error.

        Args:
            mocker (AsyncMock): Mock object
        """
        mocker.patch('app.auth.decode_jwt_token', side_effect=TokenExpiredError)
        with pytest.raises(HTTPException) as exc_info:
            _verify_service_token('Fake token', mocker.Mock())
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert exc_info.value.detail == RESPONSE_LEGACY_ERROR_SYSTEM_CLOCK


class TestDecodeJwtToken:
    """Test decode_jwt_token."""

    @pytest.mark.parametrize('valid_token', [True, False])
    async def test_happy_path(self, valid_token: bool, mocker: AsyncMock) -> None:
        """Test happy path.

        Args:
            valid_token (bool): True or False
            mocker (AsyncMock): Mock object
        """
        mocker.patch('app.auth.jwt.decode', return_value='Fake token')
        mocker.patch('app.auth.validate_jwt_token', return_value=valid_token)
        assert decode_jwt_token('Fake token', mocker.Mock()) is valid_token

    @pytest.mark.parametrize(
        'test_exception', [jwt.InvalidIssuedAtError, jwt.ImmatureSignatureError, jwt.ExpiredSignatureError]
    )
    async def test_token_expired(self, test_exception: Exception, mocker: AsyncMock) -> None:
        """Test token expired exception is raised.

        Args:
            test_exception (Exception): Exception to raise
            mocker (AsyncMock): Mock object
        """
        mocker.patch.object(jwt, 'decode', side_effect=test_exception)
        mocker.patch('app.auth.decode_token')
        with pytest.raises(TokenExpiredError):
            decode_jwt_token('Fake token', mocker.Mock())

    @pytest.mark.parametrize('test_exception', [jwt.InvalidAlgorithmError, NotImplementedError])
    async def test_token_algorithm_error(self, test_exception: Exception, mocker: AsyncMock) -> None:
        """Test algorithm exception is raised.

        Args:
            test_exception (Exception): Exception to raise
            mocker (AsyncMock): Mock object
        """
        mocker.patch.object(jwt, 'decode', side_effect=test_exception)
        with pytest.raises(TokenAlgorithmError):
            decode_jwt_token('Fake token', mocker.Mock())


class TestJwtBearer:
    """Test JWTBearer class."""

    async def test_happy_path(self, mocker: AsyncMock) -> None:
        """Test happy path.

        Args:
            mocker (AsyncMock): Mock object
        """
        auth = JWTBearer()
        request = mocker.AsyncMock(spec=Request)
        mocker.patch('app.auth.HTTPBearer.__call__', return_value=None)
        mock_credentials = mocker.Mock()
        mock_credentials.credentials = 'Fake token'
        mocker.patch('app.auth.get_token_issuer')
        mocker.patch('app.auth.verify_service_token')
        with patch.object(HTTPBearer, '__call__', new_callable=AsyncMock) as mock_parent_call:
            mock_parent_call.return_value = mock_credentials
            await auth(request)

    async def test_no_auth(self, mocker: AsyncMock) -> None:
        """Test no auth fail is compatible with notification-api.

        Args:
            mocker (AsyncMock): Mock object
        """
        auth = JWTBearer()
        request = mocker.AsyncMock(spec=Request)
        request.headers = {}
        with pytest.raises(HTTPException) as exc_info:
            await auth(request)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert exc_info.value.detail == RESPONSE_403

    @pytest.mark.parametrize('bearer', ['', 'Bearer', ' Bearer'])
    async def test_invalid_auth(self, bearer: str, mocker: AsyncMock) -> None:
        """Test invalid auth fail is compatible with notification-api.

        Args:
            bearer (str): Bearer keyword, no the token
            mocker (AsyncMock): Mock object
        """
        auth = JWTBearer()
        request = mocker.AsyncMock(spec=Request)
        request.headers = {'Authorization': bearer}
        with pytest.raises(HTTPException) as exc_info:
            await auth(request)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert exc_info.value.detail == RESPONSE_403

    async def test_no_credentials(self, mocker: AsyncMock) -> None:
        """Test no credentials fail is compatible with notification-api.

        Args:
            mocker (AsyncMock): Mock object
        """
        auth = JWTBearer()
        request = mocker.AsyncMock(spec=Request)
        mocker.patch('app.auth.HTTPBearer.__call__', return_value=None)
        with patch.object(HTTPBearer, '__call__', new_callable=AsyncMock) as mock_parent_call:
            mock_parent_call.return_value = None
            with pytest.raises(HTTPException) as exc_info:
                await auth(request)
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert exc_info.value.detail == RESPONSE_LEGACY_NO_CREDENTIALS


class TestJwtBearerAdmin:
    """Test JWTBearerAdmin class."""

    async def test_happy_path(self, mocker: AsyncMock) -> None:
        """Test happy path.

        Args:
            mocker (AsyncMock): Mock object
        """
        auth = JWTBearerAdmin()
        request = mocker.AsyncMock(spec=Request)
        mocker.patch('app.auth.HTTPBearer.__call__', return_value=None)
        mock_credentials = mocker.Mock()
        mock_credentials.credentials = 'Fake token'
        mocker.patch('app.auth.verify_admin_token', return_value=True)
        with patch.object(HTTPBearer, '__call__', new_callable=AsyncMock) as mock_parent_call:
            mock_parent_call.return_value = mock_credentials
            await auth(request)

    async def test_no_auth(self, mocker: AsyncMock) -> None:
        """Test no auth fail is compatible with notification-api.

        Args:
            mocker (AsyncMock): Mock object
        """
        auth = JWTBearerAdmin()
        request = mocker.AsyncMock(spec=Request)
        request.headers = {}
        with pytest.raises(HTTPException) as exc_info:
            await auth(request)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert exc_info.value.detail == RESPONSE_403

    @pytest.mark.parametrize('bearer', ['', 'Bearer', ' Bearer'])
    async def test_invalid_auth(self, bearer: str, mocker: AsyncMock) -> None:
        """Test invalid auth fail is compatible with notification-api.

        Args:
            bearer (str): Bearer keyword, no the token
            mocker (AsyncMock): Mock object
        """
        auth = JWTBearerAdmin()
        request = mocker.AsyncMock(spec=Request)
        request.headers = {'Authorization': bearer}
        with pytest.raises(HTTPException) as exc_info:
            await auth(request)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert exc_info.value.detail == RESPONSE_403

    async def test_no_credentials(self, mocker: AsyncMock) -> None:
        """Test no credentials fail is compatible with notification-api.

        Args:
            mocker (AsyncMock): Mock object
        """
        auth = JWTBearerAdmin()
        request = mocker.AsyncMock(spec=Request)
        mocker.patch('app.auth.HTTPBearer.__call__', return_value=None)
        with patch.object(HTTPBearer, '__call__', new_callable=AsyncMock) as mock_parent_call:
            mock_parent_call.return_value = None
            with pytest.raises(HTTPException) as exc_info:
                await auth(request)
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert exc_info.value.detail == RESPONSE_LEGACY_NO_CREDENTIALS

    async def test_fails_admin_verify(self, mocker: AsyncMock) -> None:
        """Test bad admin credentials fail is compatible with notification-api.

        Args:
            mocker (AsyncMock): Mock object
        """
        auth = JWTBearerAdmin()
        request = mocker.AsyncMock(spec=Request)
        mocker.patch('app.auth.HTTPBearer.__call__', return_value=None)
        mock_credentials = mocker.Mock()
        mock_credentials.credentials = 'Fake token'
        mocker.patch('app.auth.verify_admin_token', return_value=False)
        with patch.object(HTTPBearer, '__call__', new_callable=AsyncMock) as mock_parent_call:
            mock_parent_call.return_value = mock_credentials
            with pytest.raises(HTTPException) as exc_info:
                await auth(request)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert exc_info.value.detail == RESPONSE_LEGACY_INVALID_TOKEN_NOT_VALID


class TestDecodeToken:
    """Test decode_token method."""

    def test_decode_token_success(self) -> None:
        """Test a token can be successfully decoded."""
        payload = {'message': 'this is a test'}
        token = jwt.encode(payload, ADMIN_SECRET_KEY, headers={'typ': 'JWT', 'alg': ALGORITHM})
        assert decode_token(token) == payload

    def test_decode_token_invalid(self) -> None:
        """Test we cannot decode fake tokens."""
        with pytest.raises(jwt.DecodeError):
            decode_token('Fake token')


class TestValidateJwtToken:
    """Test validate_jwt_token method."""

    def test_happy_path(self) -> None:
        """Test happy path."""
        secret = 'Fake secret'
        issuer = 'Fake issuer'
        payload = JWTPayloadDict(
            iss=issuer,
            iat=int(time.time()),
            exp=(int(time.time()) + 30),
        )
        token = jwt.encode(dict(payload), secret, headers={'typ': 'JWT', 'alg': ALGORITHM})
        validate_jwt_token(decode_token(token))

    def test_no_iss(self) -> None:
        """Test no iss."""
        secret = 'Fake secret'
        payload = {
            'iat': int(time.time()),
            'exp': (int(time.time()) + 30),
        }
        token = jwt.encode(payload, secret, headers={'typ': 'JWT', 'alg': ALGORITHM})
        with pytest.raises(TokenIssuerError):
            validate_jwt_token(decode_token(token))

    def test_no_iat(self) -> None:
        """Test no iat."""
        secret = 'Fake secret'
        issuer = 'Fake issuer'
        payload = {
            'iss': issuer,
            'exp': (int(time.time()) + 30),
        }
        token = jwt.encode(payload, secret, headers={'typ': 'JWT', 'alg': ALGORITHM})
        with pytest.raises(TokenIssuedAtError):
            validate_jwt_token(decode_token(token))

    def test_expired(self) -> None:
        """Test an iat taht was a long time ago."""
        secret = 'Fake secret'
        issuer = 'Fake issuer'
        payload = JWTPayloadDict(
            iss=issuer,
            iat=int(time.time()) - 300,  # 5 minutes ago
            exp=(int(time.time())),
        )
        token = jwt.encode(dict(payload), secret, headers={'typ': 'JWT', 'alg': ALGORITHM})
        with pytest.raises(TokenExpiredError):
            validate_jwt_token(decode_token(token))

    def test_future(self) -> None:
        """Test an iat in the future."""
        secret = 'Fake secret'
        issuer = 'Fake issuer'
        payload = JWTPayloadDict(
            iss=issuer,
            iat=int(time.time()) + 300,  # In 5 minutes
            exp=(int(time.time())) + 330,
        )
        token = jwt.encode(dict(payload), secret, headers={'typ': 'JWT', 'alg': ALGORITHM})
        with pytest.raises(TokenExpiredError):
            validate_jwt_token(decode_token(token))


class TestInternalGetTokenIssuer:
    """Test _get_token_issuer method."""

    def test_happy_path(self) -> None:
        """Test happy path."""
        secret = 'Fake secret'
        issuer = 'Fake issuer'
        payload = JWTPayloadDict(
            iss=issuer,
            iat=int(time.time()),
            exp=(int(time.time()) + 30),
        )
        token = jwt.encode(dict(payload), secret, headers={'typ': 'JWT', 'alg': ALGORITHM})
        assert _get_token_issuer(token) == issuer

    def test_decode_error(self, mocker: AsyncMock) -> None:
        """Test decode error.

        Args:
            mocker (AsyncMock): Mock object
        """
        mocker.patch('app.auth.decode_token', side_effect=jwt.DecodeError)
        with pytest.raises(TokenDecodeError):
            _get_token_issuer('Fake token')

    def test_no_iss(self) -> None:
        """Test no issuer."""
        secret = 'Fake secret'
        payload = {
            'iat': int(time.time()),
            'exp': (int(time.time()) + 30),
        }
        token = jwt.encode(payload, secret, headers={'typ': 'JWT', 'alg': ALGORITHM})
        with pytest.raises(TokenIssuerError):
            _get_token_issuer(token)


class TestGetTokenIssuer:
    """Test get_token_issuer method."""

    issuer = 'Fake issuer'

    @pytest.fixture
    def token(self) -> str:
        """Generate a bearer token.

        Returns:
            str: The token
        """
        secret = 'Fake secret'
        payload = JWTPayloadDict(
            iss=TestGetTokenIssuer.issuer,
            iat=int(time.time()),
            exp=(int(time.time()) + 30),
        )
        return jwt.encode(dict(payload), secret, headers={'typ': 'JWT', 'alg': ALGORITHM})

    def test_happy_path(self, token: str) -> None:
        """Test happy path.

        Args:
            token (str): An encoded token
        """
        assert get_token_issuer(token) == TestGetTokenIssuer.issuer

    def test_issuer_error(self, mocker: AsyncMock) -> None:
        """Test invalid issuers are caught.

        Args:
            mocker (AsyncMock): Mock object
        """
        mocker.patch('app.auth._get_token_issuer', side_effect=TokenIssuerError)
        with pytest.raises(HTTPException) as exc_info:
            get_token_issuer('Fake token')
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert exc_info.value.detail == RESPONSE_LEGACY_INVALID_TOKEN_NO_ISS

    def test_decode_error(self, mocker: AsyncMock) -> None:
        """Test fake tokens are caught.

        Args:
            mocker (AsyncMock): Mock object
        """
        mocker.patch('app.auth._get_token_issuer', side_effect=TokenDecodeError)
        with pytest.raises(HTTPException) as exc_info:
            get_token_issuer('Fake token')
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert exc_info.value.detail == RESPONSE_LEGACY_INVALID_TOKEN_NOT_VALID


class TestValidateServiceApiKey:
    """Test _validate_service_api_key method."""

    def test_happy_path(self) -> None:
        """Test happy path."""
        service_id = uuid4()
        expiry = datetime(2222, 12, 31, tzinfo=timezone.utc)
        api_key = ApiKeyRecord(uuid4(), encode_and_sign('fake secret'), service_id, expiry, False, 'normal')
        _validate_service_api_key(api_key, str(service_id), 'fake name')

    def test_revoked(self) -> None:
        """Test with a revoked key."""
        service_id = uuid4()
        expiry = datetime(2222, 12, 31, tzinfo=timezone.utc)
        api_key = ApiKeyRecord(uuid4(), encode_and_sign('fake secret'), service_id, expiry, True, 'normal')
        with pytest.raises(HTTPException) as exc_info:
            _validate_service_api_key(api_key, str(service_id), 'fake name')
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert exc_info.value.detail == RESPONSE_LEGACY_INVALID_TOKEN_REVOKED

    def test_expired(self) -> None:
        """Test with an expired key."""
        service_id = uuid4()
        expiry = datetime(2000, 1, 1, tzinfo=timezone.utc)
        api_key = ApiKeyRecord(uuid4(), encode_and_sign('fake secret'), service_id, expiry, False, 'normal')
        _validate_service_api_key(api_key, str(service_id), 'fake name')

    def test_no_expiry(self) -> None:
        """Test with no expiry_date."""
        service_id = uuid4()
        api_key = ApiKeyRecord(uuid4(), encode_and_sign('fake secret'), service_id, None, False, 'normal')
        _validate_service_api_key(api_key, str(service_id), 'fake name')


class TestGetActiveServiceForIssuer:
    """Test class for get_active_service_for_issuer method."""

    async def test_happy_path(self, mocker: AsyncMock) -> None:
        """Test happy path.

        Args:
            mocker (AsyncMock): Mock object
        """
        service_id = uuid4()
        mock_service = mocker.patch('app.auth.LegacyServiceDao.get', new_callable=AsyncMock)
        mock_service.active = True
        mock_service.id = service_id

        await get_active_service_for_issuer(str(service_id))

    @pytest.mark.parametrize('test_exception', [RetryableError, NonRetryableError])
    async def test_service_lookup_failure(self, test_exception: Exception, mocker: AsyncMock) -> None:
        """Test what happens when a service is not found.

        Args:
            test_exception (Exception): Exception to be tested
            mocker (AsyncMock): Mock object
        """
        service_id = uuid4()
        mocker.patch('app.auth.LegacyServiceDao.get', side_effect=test_exception)
        with pytest.raises(HTTPException) as exc_info:
            await get_active_service_for_issuer(str(service_id))
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert exc_info.value.detail == RESPONSE_LEGACY_INVALID_TOKEN_NO_SERVICE

    async def test_inactive_service(self, mocker: AsyncMock) -> None:
        """Test for an inactive service.

        Args:
            mocker (AsyncMock): Mock object
        """
        service_id = uuid4()
        mock_service = mocker.AsyncMock()
        mock_service.active = False
        mock_service.id = service_id
        mocker.patch('app.auth.LegacyServiceDao.get', return_value=mock_service, new_callable=AsyncMock)
        with pytest.raises(HTTPException) as exc_info:
            await get_active_service_for_issuer(str(service_id))
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert exc_info.value.detail == RESPONSE_LEGACY_INVALID_TOKEN_ARCHIVED_SERVICE

    async def test_invalid_uuid_for_issuer(self) -> None:
        """Test for an invalid issuer."""
        with pytest.raises(HTTPException) as exc_info:
            await get_active_service_for_issuer('not a uuid')
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert exc_info.value.detail == RESPONSE_LEGACY_INVALID_TOKEN_WRONG_TYPE
