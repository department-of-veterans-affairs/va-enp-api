"""Test legacy auth."""

import time
from datetime import UTC, datetime, timedelta
from typing import Any, Awaitable, Callable, Type
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import jwt
import pytest
from fastapi import HTTPException, Request
from sqlalchemy import Row
from sqlalchemy.exc import DataError, NoResultFound

from app.auth import (
    ACCESS_TOKEN_EXPIRE_SECONDS,
    JWTPayloadDict,
    TokenAlgorithmError,
    TokenDecodeError,
    TokenError,
    TokenExpiredError,
    TokenIssuedAtError,
    TokenIssuerError,
    _validate_service_api_key,
    _verify_service_token,
    decode_jwt_token,
    get_active_service_for_issuer,
    get_token_issuer,
    validate_jwt_token,
    verify_service_token,
)
from app.legacy.dao.api_keys_dao import ApiKeyRecord, encrypt
from tests.conftest import generate_token, generate_token_with_partial_payload


async def test_verify_service_token_with_valid_token_and_service(
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
    encrypted_secret = encrypt(secret)
    api_key = await sample_api_key(service_id=service.id, secret=encrypted_secret)

    current_timestamp = int(time.time())
    payload: JWTPayloadDict = {
        'iss': str(service.id),
        'iat': current_timestamp,
        'exp': current_timestamp + 60,
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


async def test_verify_service_token_raises_with_no_api_keys(
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

    current_timestamp = int(time.time())
    payload: JWTPayloadDict = {
        'iss': str(service.id),
        'iat': current_timestamp,
        'exp': current_timestamp + 60,
    }
    token = generate_token(sig_key='not_so_secret', payload=payload)

    request = Mock(spec=Request)

    with (
        patch('app.auth.LegacyServiceDao.get_service', new=AsyncMock(return_value=service)),
        patch('app.auth.LegacyApiKeysDao.get_api_keys', side_effect=NoResultFound),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await verify_service_token(issuer=payload['iss'], token=token, request=request)

        exc = exc_info.value
        assert exc.status_code == 403
        assert exc.detail == 'Invalid token: service has no API keys'


async def test_verify_service_token_raises_with_no_matching_api_key_secret(
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
    api_key = await sample_api_key(service_id=service.id)

    current_timestamp = int(time.time())
    payload: JWTPayloadDict = {
        'iss': str(service.id),
        'iat': current_timestamp,
        'exp': current_timestamp + 60,
    }
    token = generate_token(sig_key='not_so_secret', payload=payload)

    request = Mock(spec=Request)

    with (
        patch('app.auth.LegacyServiceDao.get_service', new=AsyncMock(return_value=service)),
        patch('app.auth.LegacyApiKeysDao.get_api_keys', new=AsyncMock(return_value=[api_key])),
        patch('app.auth.ApiKeyRecord.secret', new=None),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await verify_service_token(issuer=payload['iss'], token=token, request=request)

        exc = exc_info.value
        assert exc.status_code == 403
        assert exc.detail == 'Invalid token: signature, api token not found'


async def test_verify_service_token_raises_with_no_valid_api_keys(
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
    encrypted_secret = encrypt(secret)
    api_key = await sample_api_key(service_id=service.id, secret=encrypted_secret)

    current_timestamp = int(time.time())
    payload: JWTPayloadDict = {
        'iss': str(service.id),
        'iat': current_timestamp,
        'exp': current_timestamp + 60,
    }
    token = generate_token(sig_key='not_so_secret', payload=payload)

    # Create a mock FastAPI request with state
    request = Mock(spec=Request)

    with (
        patch('app.auth.LegacyServiceDao.get_service', new=AsyncMock(return_value=service)),
        patch('app.auth.LegacyApiKeysDao.get_api_keys', new=AsyncMock(return_value=[api_key])),
        patch('app.auth._verify_service_token', new=Mock(return_value=False)),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await verify_service_token(issuer=payload['iss'], token=token, request=request)

        exc = exc_info.value
        assert exc.status_code == 403
        assert exc.detail == 'Invalid token: signature, api token not found'


async def test_get_active_service_for_issuer_with_invalid_issuer() -> None:
    """Should raise 403 if the issuer is not a valid UUID4 string."""
    with pytest.raises(HTTPException) as exc_info:
        await get_active_service_for_issuer('not-a-uuid')

    exc = exc_info.value
    assert exc.status_code == 403
    assert exc.detail == 'Invalid token: service id is not the right data type'


@pytest.mark.parametrize(
    ('raises', 'expected_detail'),
    [
        (DataError, 'Invalid token: service id is not the right data type'),
        (NoResultFound, 'Invalid token: service not found'),
    ],
)
async def test_get_active_service_for_issuer_with_invalid_service_id(
    raises: Type[Exception], expected_detail: str
) -> None:
    """Should raise 403 with correct detail if the service ID is invalid or not found."""
    issuer = str(uuid4())

    with patch('app.auth.LegacyServiceDao.get_service', side_effect=raises):
        with pytest.raises(HTTPException) as exc_info:
            await get_active_service_for_issuer(issuer)

    exc = exc_info.value
    assert exc.status_code == 403
    assert exc.detail == expected_detail


async def test_get_active_service_for_issuer_with_inactive_service(
    sample_service: Callable[..., Awaitable[Row[Any]]],
) -> None:
    """Should raise 403 if the service is archived (inactive)."""
    service = await sample_service(active=False)
    issuer = str(service.id)

    with patch('app.auth.LegacyServiceDao.get_service', new=AsyncMock(return_value=service)):
        with pytest.raises(HTTPException) as exc_info:
            await get_active_service_for_issuer(issuer)

    exc = exc_info.value
    assert exc.status_code == 403
    assert exc.detail == 'Invalid token: service is archived'


def test_verify_service_token_with_bad_token() -> None:
    """Should return False for an invalid JWT token."""
    secret = 'not_so_secret'
    encrypted_secret = encrypt(secret)
    api_key = ApiKeyRecord(
        id=uuid4(),
        _secret_encrypted=encrypted_secret,
        service_id=uuid4(),
        expiry_date=None,
        revoked=False,
    )
    assert not _verify_service_token('not_a_valid_token', api_key)


def test_verify_service_token_with_expired_token() -> None:
    """Should raise 403 if the token is issued too far in the future."""
    secret = 'not_so_secret'
    encrypted_secret = encrypt(secret)
    service_id = uuid4()
    api_key = ApiKeyRecord(
        id=uuid4(),
        _secret_encrypted=encrypted_secret,
        service_id=uuid4(),
        expiry_date=None,
        revoked=False,
    )
    current_timestamp = int(time.time())
    partial_payload = {
        'iss': str(service_id),
        'iat': current_timestamp + (2 * ACCESS_TOKEN_EXPIRE_SECONDS),
    }
    token = generate_token_with_partial_payload(sig_key='not_so_secret', payload=partial_payload)

    with pytest.raises(HTTPException) as exc_info:
        _verify_service_token(token, api_key)

    exc = exc_info.value
    assert exc.status_code == 403
    assert exc.detail == 'Error: Your system clock must be accurate to within 30 seconds'


def test_validate_service_api_key_raises_with_revoked_key() -> None:
    """Should raise 403 if the API key is revoked."""
    service_id = uuid4()
    service_name = 'sample service'
    api_key = ApiKeyRecord(
        id=uuid4(),
        _secret_encrypted='encrypted_secret',
        service_id=service_id,
        expiry_date=None,
        revoked=True,
    )
    with pytest.raises(HTTPException) as exc_info:
        _validate_service_api_key(api_key, str(service_id), service_name)

    exc = exc_info.value
    assert exc.status_code == 403
    assert exc.detail == 'Invalid token: API key revoked'


def test_validate_service_api_key_logs_warning_with_no_expiry() -> None:
    """Should log a warning if the API key has no expiry date."""
    service_id = uuid4()
    service_name = 'sample service'
    api_key = ApiKeyRecord(
        id=uuid4(),
        _secret_encrypted='encrypted_secret',
        service_id=service_id,
        expiry_date=None,
        revoked=False,
    )

    with patch('app.auth.logger.warning') as mock_warning:
        _validate_service_api_key(api_key, str(service_id), service_name)

        mock_warning.assert_called_once_with(
            'service {} - {} used old-style api key {} with no expiry_date',
            str(service_id),
            service_name,
            api_key.id,
        )


def test_validate_service_api_key_logs_warning_with_expired_key() -> None:
    """Should log a warning if the API key is expired."""
    service_id = uuid4()
    service_name = 'sample service'
    api_key = ApiKeyRecord(
        id=uuid4(),
        _secret_encrypted='encrypted_secret',
        service_id=service_id,
        expiry_date=datetime.now(UTC) - timedelta(days=1),
        revoked=False,
    )

    with patch('app.auth.logger.warning') as mock_warning:
        _validate_service_api_key(api_key, str(service_id), service_name)

        mock_warning.assert_called_once_with(
            'service {} - {} used expired api key {} expired as of {}',
            str(service_id),
            service_name,
            api_key.id,
            api_key.expiry_date,
        )


def test_get_token_issuer_raises_unable_to_decode() -> None:
    """Should raise TokenDecodeError if the token cannot be decoded."""
    with pytest.raises(HTTPException) as exc_info:
        get_token_issuer('not a valid token')

    exc = exc_info.value
    assert exc.status_code == 403
    assert exc.detail == 'Invalid token: signature, api token is not valid'


def test_get_token_issuer_raises_with_missing_issuer() -> None:
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


def test_decode_jwt_token_raises_with_invalid_algorithm() -> None:
    """Should raise TokenAlgorithmError if the token uses an unexpected algorithm."""
    current_timestamp = int(time.time())
    payload: JWTPayloadDict = {
        'iss': 'sample service',
        'iat': current_timestamp,
        'exp': current_timestamp + 60,
    }

    headers = {
        'typ': 'JWT',
        'alg': 'HS384',
    }

    token = jwt.encode(dict(payload), 'not_so_secret', headers=headers)

    with pytest.raises(TokenAlgorithmError):
        decode_jwt_token(token, 'not_so_secret')


def test_decode_jwt_token_raises_with_invalid_token() -> None:
    """Should raise TokenError if jwt.decode raises InvalidTokenError."""
    with patch('app.auth.jwt.decode', side_effect=jwt.InvalidTokenError):
        with pytest.raises(TokenError):
            decode_jwt_token('invalid_token', 'not_so_secret')


def test_validate_jwt_token_raises_with_missing_issuer() -> None:
    """Should raise TokenIssuerError if the token is missing the 'iss' claim."""
    current_timestamp = int(time.time())
    payload = {
        'iat': current_timestamp,
        'exp': current_timestamp,
    }
    with pytest.raises(TokenIssuerError):
        validate_jwt_token(payload)


def test_validate_jwt_token_raises_with_missing_issued_at() -> None:
    """Should raise TokenIssuedAtError if the token is missing the 'iat' claim."""
    current_timestamp = int(time.time())
    partial_payload = {
        'iss': 'sample service',
        'exp': current_timestamp + 60,
    }
    with pytest.raises(TokenIssuedAtError):
        validate_jwt_token(partial_payload)


def test_validate_jwt_token_raises_with_expired_token() -> None:
    """Should raise TokenExpiredError if the token is expired."""
    current_timestamp = int(time.time())
    partial_payload = {
        'iss': 'sample service',
        'iat': current_timestamp - ACCESS_TOKEN_EXPIRE_SECONDS - 1,
    }
    with pytest.raises(TokenExpiredError):
        validate_jwt_token(partial_payload)


def test_validate_jwt_token_raises_with_future_token() -> None:
    """Should raise TokenExpiredError if the token is issued too far in the future."""
    current_timestamp = int(time.time())
    partial_payload = {
        'iss': 'sample service',
        'iat': current_timestamp + (2 * ACCESS_TOKEN_EXPIRE_SECONDS),
    }
    with pytest.raises(TokenExpiredError):
        validate_jwt_token(partial_payload)


# Error tests


def test_token_expired_error_instantiation() -> None:
    """Should instantiate TokenExpiredError with message and token."""
    minimal_token = {
        'iss': 'sample service',
        'iat': 0,
    }
    err = TokenExpiredError('token expired', token=minimal_token)
    assert isinstance(err, TokenExpiredError)
    assert err.message == 'token expired'
    assert err.token == minimal_token


def test_token_algorithm_error_instantiation() -> None:
    """Should instantiate TokenAlgorithmError with the correct message."""
    err = TokenAlgorithmError()
    assert isinstance(err, TokenAlgorithmError)
    assert 'algorithm used is not' in err.message


def test_token_decode_error_with_message() -> None:
    """Should instantiate TokenDecodeError with a custom message."""
    err = TokenDecodeError('bad signature')
    assert isinstance(err, TokenDecodeError)
    assert err.message == 'bad signature'


def test_token_decode_error_without_message() -> None:
    """Should instantiate TokenDecodeError with the default message."""
    err = TokenDecodeError()
    assert err.message == 'Invalid token: signature'


def test_token_issuer_error_instantiation() -> None:
    """Should instantiate TokenIssuerError with the correct message."""
    err = TokenIssuerError()
    assert isinstance(err, TokenIssuerError)
    assert err.message == 'Invalid token: iss field not provided'


def test_token_issued_at_error_instantiation() -> None:
    """Should instantiate TokenIssuedAtError with the correct message."""
    err = TokenIssuedAtError()
    assert isinstance(err, TokenIssuedAtError)
    assert err.message == 'Invalid token: iat field not provided'
