"""This module contains authentication methods used to verify the JWT token sent by clients."""

import os
from typing import Optional

import jwt
from fastapi import HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from loguru import logger

ADMIN_SECRET_KEY = os.getenv('ENP_ADMIN_SECRET_KEY')
ALGORITHM = os.getenv('ENP_ALGORITHM', 'HS256')
ACCESS_TOKEN_EXPIRE_SECONDS = int(os.getenv('ENP_ACCESS_TOKEN_EXPIRE_SECONDS', 60))


class JWTBearer(HTTPBearer):
    """JWTBearer class to verify the JWT token sent by the client."""

    def __init__(self, auto_error: bool = True) -> None:
        """Initialize the JWTBearer class.

        Args:
            auto_error (bool, optional): If True, raise an HTTPException if the token is invalid or expired. Defaults to True.
        """
        super(JWTBearer, self).__init__(auto_error=auto_error)

    async def __call__(self, request: Request) -> Optional[HTTPAuthorizationCredentials]:
        """Override the __call__ method to verify the JWT token. A JWT token is considered valid if it is not expired, and the signature is valid.

        Args:
            request (Request): FastAPI request object

        Returns:
            Optional[HTTPAuthorizationCredentials]: HTTPAuthorizationCredentials object if the token is valid, None otherwise.

        Raises:
            HTTPException: If the token is invalid or expired
        """
        credentials: HTTPAuthorizationCredentials | None = await super(JWTBearer, self).__call__(request)
        if credentials is None:
            raise HTTPException(status_code=403, detail='Not authenticated')
        if not self.verify_token(str(credentials.credentials)):
            raise HTTPException(status_code=403, detail='Invalid token or expired token.')
        return credentials

    def verify_token(self, jwtoken: str) -> bool:
        """Verify the JWT token and check if it is expired.

        Args:
            jwtoken (str): JWT token

        Returns:
            bool: True if the token is valid and not expired, False otherwise.
        """
        try:
            payload = jwt.decode(
                jwtoken,
                ADMIN_SECRET_KEY,
                algorithms=[ALGORITHM],
                options={
                    'verify_signature': True,
                },
            )
            logger.info('JWT payload: {}', payload)
            return True
        except (jwt.PyJWTError, jwt.ImmatureSignatureError):
            return False
