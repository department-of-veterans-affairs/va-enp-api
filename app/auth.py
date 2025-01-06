"""This module contains authentication methods used to verify the JWT token sent by clients."""

import os
import time
from typing import TypedDict

import jwt
from fastapi import HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from loguru import logger

ADMIN_SECRET_KEY = os.getenv('ENP_ADMIN_SECRET_KEY', 'not-very-secret')
ALGORITHM = os.getenv('ENP_ALGORITHM', 'HS256')
ACCESS_TOKEN_EXPIRE_SECONDS = int(os.getenv('ENP_ACCESS_TOKEN_EXPIRE_SECONDS', 60))


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


def generate_token(sig_key: str = ADMIN_SECRET_KEY, payload: JWTPayloadDict | None = None) -> str:
    """Generate a JWT token.

    Args:
        sig_key (str): The key to sign the JWT token with.
        payload (JWTPayloadDict): The payload to include in the JWT token.

    Returns:
        str: The signed JWT token.
    """
    headers = {
        'typ': 'JWT',
        'alg': ALGORITHM,
    }
    if payload is None:
        payload = JWTPayloadDict(
            iss='enp',
            iat=int(time.time()),
            exp=int(time.time()) + ACCESS_TOKEN_EXPIRE_SECONDS,
        )
    return jwt.encode(payload.__dict__, sig_key, headers=headers)


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
            logger.exception('No credentials provided.')
            raise HTTPException(status_code=403, detail='Not authenticated')
        if not verify_token(str(credentials.credentials)):
            logger.exception('Invalid token or expired token.')
            raise HTTPException(status_code=403, detail='Invalid token or expired token.')
        return credentials
