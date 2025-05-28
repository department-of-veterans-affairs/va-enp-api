"""The data access objects for API keys."""

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Sequence

from loguru import logger
from pydantic import UUID4
from sqlalchemy import Row, select
from sqlalchemy.exc import (
    DataError,
    InterfaceError,
    OperationalError,
    SQLAlchemyError,
    TimeoutError,
)

from app.db.db_init import get_read_session_with_context, metadata_legacy
from app.exceptions import NonRetryableError, RetryableError


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
            Sequence[Row[Any]]: A sequence of rows from the 'api_keys' table, each representing an API key
            associated with the specified service.

        Raises:
            RetryableError: If the failure is likely transient (e.g., connection error).
            NonRetryableError: If the failure is deterministic (e.g., bad input).
        """
        legacy_api_keys = metadata_legacy.tables['api_keys']
        stmt = select(legacy_api_keys).where(legacy_api_keys.c.service_id == service_id)

        try:
            async with get_read_session_with_context() as session:
                result = await session.execute(stmt)

            return result.fetchall()

        except DataError as e:
            # Deterministic and will likely fail again
            logger.exception(
                'Service API keys lookup failed, invalid or unexpected data for service_id: {}', service_id
            )
            raise NonRetryableError('Service API keys lookup failed, invalid or unexpected data') from e

        except (OperationalError, InterfaceError, TimeoutError) as e:
            # Transient DB issues that may succeed on retry
            fail_message = 'Service API keys lookup failed due to a transient database error.'
            logger.warning(fail_message)
            raise RetryableError(fail_message) from e

        except SQLAlchemyError as e:
            logger.exception('Uexpected SQLAlchemy error during service API keys lookup for service_id: {}', service_id)
            raise NonRetryableError('Uexpected SQLAlchemy error during service API keys lookup.') from e


@dataclass
class ApiKeyRecord:
    """Represents a single API key record, including metadata and the encrypted secret.

    Attributes:
        id (UUID4): The unique identifier of the API key.
        _secret_encrypted (str): The encrypted secret string for the API key.
        service_id (UUID4): The ID of the service this API key belongs to.
        expiry_date (datetime | None): The expiration date of the API key, if any.
        revoked (bool): Indicates whether the API key has been revoked.
    """

    id: UUID4
    _secret_encrypted: str
    service_id: UUID4
    expiry_date: datetime | None
    revoked: bool

    @property
    def secret(self) -> str:
        """Decode and return the API key's secret.

        Returns:
            str: The decoded secret

        Raises:
            NonRetryableError: If the secret cannot be decoded.
        """
        try:
            return decode_and_remove_signature(self._secret_encrypted)
        except NonRetryableError:
            logger.error(
                'Failed to decode API key secret for service_id: {} api_key_id: {}',
                self.service_id,
                self.id,
            )
            raise

    @classmethod
    def from_row(cls, row: Row[Any]) -> 'ApiKeyRecord':
        """Create an ApiKeyRecord instance from a SQLAlchemy Core result row.

        Args:
            row (Row[Any]): A database row containing fields for an API key.

        Returns:
            ApiKeyRecord: A populated instance of the ApiKeyRecord class.
        """
        expiry = row.expiry_date
        if expiry is not None:
            expiry = expiry if expiry.tzinfo else expiry.replace(tzinfo=timezone.utc)

        return cls(
            id=row.id,
            _secret_encrypted=row.secret,
            service_id=row.service_id,
            expiry_date=expiry,
            revoked=row.revoked,
        )


# TODO: TEAM-1664 temp "decrypt" until isdangerous added or proper encryption implemented
# does not verify signature
def decode_and_remove_signature(encoded: str) -> str:
    """Base64url-decode the first segment of a token and remove surrounding quotes.

    Args:
        encoded (str): A string with base64url-encoded segments separated by '.'.

    Returns:
        str | None: The decoded first segment as a string, with quotes stripped,
                    or None if decoding fails.

    Raises:
        NonRetryableError: decoding fails
    """
    try:
        # all included in try/catch
        first_part = encoded.split('.')[0]
        padded = first_part + '=' * (-len(first_part) % 4)
        decoded = base64.urlsafe_b64decode(padded).decode()
        value = decoded.strip('"')
    except (IndexError, ValueError, UnicodeDecodeError, Exception):
        raise NonRetryableError('Failure decoding value')
    return value
