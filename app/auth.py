"""This module contains authentication methods used to verify the JWT token sent by clients."""

import os
from typing import TypedDict

import jwt
from fastapi import HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from loguru import logger

ADMIN_SECRET_KEY = os.getenv('ENP_ADMIN_SECRET_KEY', 'not-very-secret')
ALGORITHM = os.getenv('ENP_ALGORITHM', 'HS256')
ACCESS_TOKEN_EXPIRE_SECONDS = int(os.getenv('ENP_ACCESS_TOKEN_EXPIRE_SECONDS', 3600))


class JWTPayloadDict(TypedDict):
    """Payload dictionary type."""

    iss: str
    iat: int
    exp: int


def verify_token(jwtoken: str) -> bool:
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


class JWTBearer(HTTPBearer):
    """JWTBearer class to verify the JWT token sent by the client."""

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
        if not verify_token(str(credentials.credentials)):
            logger.info('Invalid or expired token.')
            raise HTTPException(status_code=403, detail='Invalid token: signature, api token is not valid')
        return credentials
