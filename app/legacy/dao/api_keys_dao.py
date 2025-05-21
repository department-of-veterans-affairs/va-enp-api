"""The data access objects for API keys."""

import base64
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional, Sequence

from itsdangerous import URLSafeSerializer
from loguru import logger
from pydantic import UUID4
from sqlalchemy import Row, select

from app.db.db_init import get_read_session_with_context, metadata_legacy


class LegacyApiKeysDao:
    """Data access object for interacting with API keys in the legacy database schema.

    Methods:
        get_api_keys(service_id): Retrieve all API keys associated with a given service ID.
    """

    @staticmethod
    async def get_api_keys(service_id: UUID4) -> Sequence[Row[Any]]:
        """Retrieve all API keys associated with the given service ID.

        Args:
            service_id (UUID4): The unique identifier of the service whose API keys should be fetched.

        Returns:
            list[Row[Any]]: A list of rows from the 'api_keys' table, each representing an API key
            associated with the specified service.

        Notes:
            - This method uses a read-only session context.
            - The returned rows are detached SQLAlchemy Core Row objects, not ORM models.
        """
        legacy_api_keys = metadata_legacy.tables['api_keys']
        stmt = select(legacy_api_keys).where(legacy_api_keys.c.service_id == service_id)

        async with get_read_session_with_context() as session:
            result = await session.execute(stmt)

        return result.fetchall()


@dataclass
class ApiKeyRecord:
    """Represents a single API key record, including metadata and the encrypted secret.

    Attributes:
        id (UUID4): The unique identifier of the API key.
        _secret_encrypted (str): The encrypted secret string for the API key.
        service_id (UUID4): The ID of the service this API key belongs to.
        expiry_date (Optional[datetime]): The expiration date of the API key, if any.
        revoked (bool): Indicates whether the API key has been revoked.
    """

    id: UUID4
    _secret_encrypted: str
    service_id: UUID4
    expiry_date: Optional[datetime]
    revoked: bool

    @property
    def secret(self) -> Optional[str]:
        """Decrypt and return the API key's secret.

        Returns:
            Optional[str]: The decrypted secret, or None if no secret is present.

        Notes:
            If the decryption fails due to an invalid format, a ValueError may be raised.
            This is currently unhandled and should be addressed in future revisions.
        """
        if self._secret_encrypted is not None:
            # TODO: catch and log ValueError
            return decrypt(self._secret_encrypted)
        return None

    @classmethod
    def from_row(cls, row: Row[Any]) -> 'ApiKeyRecord':
        """Create an ApiKeyRecord instance from a SQLAlchemy Core result row.

        Args:
            row (Row[Any]): A database row containing fields for an API key.

        Returns:
            ApiKeyRecord: A populated instance of the ApiKeyRecord class.
        """
        return cls(
            id=row.id,
            _secret_encrypted=row.secret,
            service_id=row.service_id,
            expiry_date=row.expiry_date,
            revoked=row.revoked,
        )


# TODO: temp "decrypt" until isdangerous added or proper encryption implemented
# does not verify signature
def decrypt(encoded: str) -> str | None:
    """Base64url-decode the first segment of a token and remove surrounding quotes.

    Args:
        encoded (str): A string with base64url-encoded segments separated by '.'.

    Returns:
        str | None: The decoded first segment as a string, with quotes stripped,
                    or None if decoding fails.
    """
    try:
        first_part = encoded.split('.')[0]
        padded = first_part + '=' * (-len(first_part) % 4)
        decoded = base64.urlsafe_b64decode(padded).decode()
        value = decoded.strip('"')
        logger.exception('Decoded API key')
        return value
    except (IndexError, ValueError, UnicodeDecodeError, Exception):
        logger.exception('Failed to decode API key')
        return None


# TODO: temp "encrypt" until isdangerous added or proper encryption implemented
# does not verify signature
def encrypt(token: str) -> str:
    """Serialize and sign a string using itsdangerous.URLSafeSerializer.

    Args:
        token (str): The string to encrypt.

    Returns:
        str: A URL-safe, signed string containing the encrypted payload.
    """
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-notify-secret-key')
    DANGEROUS_SALT = os.getenv('DANGEROUS_SALT', 'dev-notify-salt ')

    serializer = URLSafeSerializer(SECRET_KEY)
    return str(serializer.dumps(token, salt=DANGEROUS_SALT))
