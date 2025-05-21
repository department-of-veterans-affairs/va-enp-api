"""This module contains authentication methods used to verify the JWT token sent by clients."""

import os
import time
from datetime import UTC, datetime
from typing import Any, TypedDict, cast
from uuid import uuid4

import jwt
from fastapi import HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from loguru import logger
from pydantic import UUID4
from sqlalchemy import Row
from sqlalchemy.exc import DataError, NoResultFound

from app.legacy.dao.api_keys_dao import ApiKeyRecord, LegacyApiKeysDao
from app.legacy.dao.services_dao import LegacyServiceDao

ADMIN_CLIENT_USER_NAME = os.getenv('ENP_ADMIN_CLIENT_USER_NAME', 'enp')
ADMIN_SECRET_KEY = os.getenv('ENP_ADMIN_SECRET_KEY', 'not-very-secret')
ALGORITHM = os.getenv('ENP_ALGORITHM', 'HS256')
ACCESS_TOKEN_EXPIRE_SECONDS = int(os.getenv('ENP_ACCESS_TOKEN_EXPIRE_SECONDS', 60))


class JWTPayloadDict(TypedDict):
    """Payload dictionary type."""

    iss: str
    iat: int
    exp: int


class TokenError(Exception):
    """Base exception for all token-related errors.

    Attributes:
        message (str): Description of the error.
        token (Any): Optional token or decoded content that caused the error.
    """

    def __init__(self, message: str | None = None, token: dict[str, Any] | None = None) -> None:
        """Initialize the TokenError.

        Args:
            message (str, optional): A custom error message. Defaults to 'Invalid token' if not provided.
            token (any, optional): Optional reference to the offending token or related data.
        """
        self.message = message if message else 'Invalid token'
        self.token = token
        super().__init__(self.message)


class TokenExpiredError(TokenError):
    """Raised when a token's 'iat' (issued at) field indicates the token is expired or prematurely issued."""

    pass


class TokenAlgorithmError(TokenError):
    """Raised when the JWT token uses an unexpected or unsupported algorithm."""

    def __init__(self) -> None:
        """Initialize the TokenAlgorithmError with a predefined error message indicating an invalid or unsupported JWT algorithm."""
        super().__init__(f'Invalid token: algorithm used is not {ALGORITHM}')


class TokenDecodeError(TokenError):
    """Raised when the token cannot be decoded, typically due to an invalid signature or malformed content."""

    def __init__(self, message: str | None = None) -> None:
        """Initialize the TokenDecodeError with an optional custom message.

        Args:
            message (str, optional): A custom error message. Defaults to
                                     'Invalid token: signature' if not provided.
        """
        super().__init__(message or 'Invalid token: signature')


class TokenIssuerError(TokenDecodeError):
    """Raised when the decoded token is missing the required 'iss' (issuer) claim."""

    def __init__(self) -> None:
        """Initialize the TokenIssuerError with a predefined message indicating that the 'iss' (issuer) field is missing from the token."""
        super().__init__('Invalid token: iss field not provided')


class TokenIssuedAtError(TokenDecodeError):
    """Raised when the decoded token is missing the required 'iat' (issued at) claim."""

    def __init__(self) -> None:
        """Initialize the TokenIssuedAtError with a predefined message indicating that the 'iat' (issued at) field is missing from the token."""
        super().__init__('Invalid token: iat field not provided')


def verify_admin_token(jwtoken: str) -> bool:
    """Verify the JWT token and check if it is expired.

    Args:
        jwtoken (str): JWT token

    Returns:
        bool: True if the token is valid and not expired, False otherwise.
    """
    response = True
    try:
        jwt.decode(
            jwtoken,
            ADMIN_SECRET_KEY,
            algorithms=[ALGORITHM],
            options={
                'verify_signature': True,
            },
        )
    except (jwt.PyJWTError, jwt.ImmatureSignatureError):
        response = False

    return response


async def verify_service_token(issuer: str, token: str, request: Request) -> None:
    """Verify a JWT token against all active API keys for a given issuer service.

    This function:
      - Retrieves the service by ID and ensures it exists and is active.
      - Retrieves all API keys associated with the service.
      - Attempts to decode the token using each API key's secret.
      - Validates that the matching API key is not revoked or expired.
      - If a valid key is found, sets authentication context on the request.

    Args:
        issuer (str): The identifier of the service attempting authentication.
        token (str): The JWT token to be validated.
        request (Request): The FastAPI request object to attach authentication context.

    Raises:
        HTTPException:
            - If the service ID is invalid or not found.
            - If the service has no API keys.
            - If the service is archived.
            - If no matching token is found.
            - If the token is expired beyond the allowed leeway.
            - If the matching API key is revoked.
    """
    # Set the id here for tracking purposes - becomes notification id
    request.state.request_id = str(uuid4())

    service = await get_active_service_for_issuer(issuer)

    # should be at botton
    request.state.service_id = service.id

    logger.info(
        'Attempting to Lookup service API keys for service_id: {}',
        service.id,
    )

    try:
        api_keys = await LegacyApiKeysDao.get_api_keys(service.id)
    except NoResultFound:
        raise HTTPException(status_code=403, detail='Invalid token: service has no API keys')

    for row in api_keys:
        api_key = ApiKeyRecord.from_row(row)
        if api_key.secret is None:
            logger.info('API key for service has no secret service_id: {} api_key_id: {}', service.id, api_key.id)
            continue

        if not _verify_service_token(token, api_key):
            logger.info('API key unable to verify service token service_id: {} api_key_id: {}', service.id, api_key.id)
            continue

        _validate_service_api_key(api_key, service.id, service.name)

        request.state.api_user = api_key
        request.state.service_id = service.id

        return

    raise HTTPException(status_code=403, detail='Invalid token: signature, api token not found')


async def get_active_service_for_issuer(issuer: str) -> Row[Any]:
    """Validate the given issuer string as a UUID4 and return the corresponding active service.

    This function performs the following:
    - Parses the issuer string into a UUID4.
    - Retrieves the corresponding service from the database using the DAO layer.
    - Verifies that the service exists and is marked as active.

    Args:
        issuer (str): The issuer value extracted from a JWT token, expected to be a UUID4 string.

    Returns:
        Row[Any]: A SQLAlchemy Core row representing the active service associated with the given issuer.

    Raises:
        HTTPException:
            - 403 if the issuer is not a valid UUID4 or wrong type.
            - 403 if the service is not found.
            - 403 if the service is found but marked as archived (inactive).
    """
    logger.info(
        'Attempting to Lookup service by issuer: {}',
        issuer,
    )

    try:
        service_id = UUID4(issuer)
        service = await LegacyServiceDao.get_service(service_id)
    except (AttributeError, ValueError, TypeError, DataError):
        raise HTTPException(status_code=403, detail='Invalid token: service id is not the right data type')
    except NoResultFound:
        raise HTTPException(status_code=403, detail='Invalid token: service not found')

    if not service.active:
        raise HTTPException(status_code=403, detail='Invalid token: service is archived')

    logger.info(
        'Found service_id: {} for issuer: {}',
        service.id,
        issuer,
    )

    return service


def _verify_service_token(token: str, api_key: ApiKeyRecord) -> bool:
    try:
        verified = decode_jwt_token(token, api_key.secret)
    except TokenDecodeError:
        verified = False
    except TokenExpiredError:
        raise HTTPException(status_code=403, detail='Error: Your system clock must be accurate to within 30 seconds')
    return verified


def _validate_service_api_key(api_key: ApiKeyRecord, service_id: str, service_name: str) -> None:
    # TODO notification-api-2309 - The revoked field is added as a temporary measure until we can implement proper use of the expiry date
    if api_key.revoked:
        raise HTTPException(status_code=403, detail='Invalid token: API key revoked')

    if api_key.expiry_date is not None and api_key.expiry_date < datetime.now(UTC):
        logger.warning(
            'service {} - {} used expired api key {} expired as of {}',
            service_id,
            service_name,
            api_key.id,
            api_key.expiry_date,
        )
    elif api_key.expiry_date is None:
        logger.warning(
            'service {} - {} used old-style api key {} with no expiry_date',
            service_id,
            service_name,
            api_key.id,
        )


def get_token_issuer(token: str) -> str:
    """Extract the issuer from a JWT token.

    Args:
        token (str): The JWT token.

    Returns:
        str: The issuer ("iss" claim) from the token.

    Raises:
        HTTPException: If the token is missing the "iss" claim or cannot be decoded.
    """
    try:
        issuer = _get_token_issuer(token)
    except TokenIssuerError:
        raise HTTPException(status_code=403, detail='Invalid token: iss field not provided')
    except TokenDecodeError:
        raise HTTPException(status_code=403, detail='Invalid token: signature, api token is not valid')
    return issuer


def _get_token_issuer(token: str) -> str:
    """Return the 'iss' claim from a JWT without verifying the signature.

    Args:
        token (str): The JWT token.

    Returns:
        str: The issuer value.

    Raises:
        TokenDecodeError: If the token is not decodable.
        TokenIssuerError: If the 'iss' field is missing.
    """
    try:
        unverified = decode_token(token)
    except jwt.DecodeError as e:
        raise TokenDecodeError from e

    if 'iss' not in unverified:
        raise TokenIssuerError

    return str(unverified.get('iss'))


def decode_jwt_token(token: str, secret: str | None) -> bool:
    """Decode and validate a JWT token using the provided client-specific secret.

    This method verifies the token's signature and ensures that required claims such as
    "iss" (issuer) and "iat" (issued at) are present and valid. It also checks that the
    token's issuance time is within an acceptable range based on configured leeway.

    Args:
        token (str): A JWT token string.
        secret (str): The shared secret or signing key for the token.

    Returns:
        bool: True if the token is valid and passes all checks.

    Raises:
        TokenExpiredError: If the "iat" value is too far in the past or future.
        TokenDecodeError: If the token fails decoding due to an invalid structure.
        TokenAlgorithmError: If the JWT specifies an invalid or unsupported algorithm.
        TokenError: For any other unhandled JWT-related validation errors.
    """
    try:
        decoded_token = jwt.decode(
            token,
            secret,
            algorithms=[ALGORITHM],
            leeway=ACCESS_TOKEN_EXPIRE_SECONDS,
            options={'verify_signature': True},
        )
        return validate_jwt_token(decoded_token)

    except (jwt.InvalidIssuedAtError, jwt.ImmatureSignatureError) as e:
        raise TokenExpiredError('Token time is invalid', decode_token(token)) from e

    except jwt.DecodeError as e:
        raise TokenDecodeError from e

    except (jwt.InvalidAlgorithmError, NotImplementedError) as e:
        raise TokenAlgorithmError from e

    except jwt.InvalidTokenError as e:
        raise TokenError from e


def validate_jwt_token(decoded_token: dict[str, Any]) -> bool:
    """Validate the contents of a decoded JWT token.

    This function performs basic validation on a decoded JWT token by:
      - Ensuring required fields ("iss" and "iat") are present.
      - Validating that the "iat" (issued at) timestamp is within acceptable bounds,
        allowing for clock skew via a configured leeway.

    Args:
        decoded_token (dict): The decoded JWT payload.

    Returns:
        bool: True if the token passes all validation checks.

    Raises:
        TokenIssuerError: If the "iss" (issuer) field is missing.
        TokenIssuedAtError: If the "iat" (issued at) field is missing.
        TokenExpiredError: If the token is expired or issued in an invalid future time.
    """
    # token has all the required fields
    if 'iss' not in decoded_token:
        raise TokenIssuerError
    if 'iat' not in decoded_token:
        raise TokenIssuedAtError

    # check iat time is within bounds
    now = int(time.time())
    iat = int(decoded_token['iat'])
    if now > (iat + ACCESS_TOKEN_EXPIRE_SECONDS):
        raise TokenExpiredError('Token has expired', decoded_token)
    if iat > (now + ACCESS_TOKEN_EXPIRE_SECONDS):
        raise TokenExpiredError('Token can not be in the future', decoded_token)

    return True


def decode_token(token: str) -> dict[str, Any]:
    """Decode a JWT token without verifying its signature.

    This method extracts and returns the payload of a JWT token. It does not
    perform any validation of the token's signature or claims.

    Args:
        token (str): A JWT token in compact serialization format.

    Returns:
        dict: The decoded payload of the JWT token.
    """
    return cast(dict[str, Any], jwt.decode(token, algorithms=[ALGORITHM], options={'verify_signature': False}))


class JWTBearerAdmin(HTTPBearer):
    """JWTBearer class to verify the JWT token sent by the client."""

    def __init__(self) -> None:
        """Initialize the authenticator with a shared OpenAPI scheme name for Swagger UI bearer token support."""
        super().__init__(scheme_name='BearerToken')

    async def __call__(self, request: Request) -> HTTPAuthorizationCredentials | None:
        """Override the __call__ method to verify the JWT token. A JWT token is considered valid if it is not expired, and the signature is valid.

        Args:
            request (Request): FastAPI request object

        Returns:
            HTTPAuthorizationCredentials | None: HTTPAuthorizationCredentials object if the token is valid, None otherwise.

        Raises:
            HTTPException: If the token is invalid or expired
        """
        credentials: HTTPAuthorizationCredentials | None = await super(JWTBearerAdmin, self).__call__(request)
        if credentials is None:
            logger.info('No credentials provided.')
            raise HTTPException(status_code=401, detail='Unauthorized, authentication token must be provided')
        if not verify_admin_token(str(credentials.credentials)):
            logger.info('Invalid or expired token.')
            raise HTTPException(status_code=403, detail='Invalid token: signature, api token is not valid')
        return credentials


class JWTBearer(HTTPBearer):
    """JWTBearer class to verify the JWT token sent by the client."""

    def __init__(self) -> None:
        """Initialize the authenticator with a shared OpenAPI scheme name for Swagger UI bearer token support."""
        super().__init__(scheme_name='BearerToken')

    async def __call__(self, request: Request) -> HTTPAuthorizationCredentials | None:
        """Override the __call__ method to verify the JWT token. A JWT token is considered valid if it is not expired, and the signature is valid.

        Args:
        request (Request): FastAPI request object

        Returns:
        HTTPAuthorizationCredentials | None: HTTPAuthorizationCredentials object if the token is valid, None otherwise.

        Raises:
        HTTPException: If the token is invalid or expired
        """
        credentials: HTTPAuthorizationCredentials | None = await super(JWTBearer, self).__call__(request)

        if credentials is None:
            logger.info('No credentials provided.')
            raise HTTPException(status_code=401, detail='Unauthorized, authentication token must be provided')

        token = str(credentials.credentials)
        issuer = get_token_issuer(token)

        if issuer != ADMIN_CLIENT_USER_NAME:
            await verify_service_token(issuer, token, request)
        elif not verify_admin_token(token):
            logger.info('Invalid or expired token.')
            raise HTTPException(status_code=403, detail='Invalid token: signature, api token is not valid')

        return credentials
