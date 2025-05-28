"""Test for API keys DAO methods."""

import os
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from itsdangerous import URLSafeSerializer
from sqlalchemy.engine import Row
from sqlalchemy.exc import (
    DataError,
    InterfaceError,
    OperationalError,
    SQLAlchemyError,
    TimeoutError,
)

from app.exceptions import NonRetryableError, RetryableError
from app.legacy.dao.api_keys_dao import ApiKeyRecord, LegacyApiKeysDao


# TODO: TEAM-1664 replace with proper encryption
def encode_and_sign(token: str) -> str:
    """Serialize and sign a string using itsdangerous.URLSafeSerializer.

    Args:
        token (str): The string to encode.

    Returns:
        str: A URL-safe, signed string containing the encoded and signed payload.
    """
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-notify-secret-key')
    DANGEROUS_SALT = os.getenv('DANGEROUS_SALT', 'dev-notify-salt ')

    serializer = URLSafeSerializer(SECRET_KEY)
    return str(serializer.dumps(token, salt=DANGEROUS_SALT))


class TestLegacyApiKeysDao:
    """Integration tests for LegacyApiKeysDao methods using committed database records.

    These tests validate the behavior of API key-related DAO operations against
    the actual database schema, ensuring that keys are correctly persisted and retrieved
    without relying on mocks or in-memory substitutes.
    """

    async def test_get_api_keys(self, prepared_api_key: Row[Any]) -> None:
        """Test that API keys can be retrieved by service ID.

        Given a committed API key associated with a sample service (via the prepared_api_key fixture),
        this test verifies that LegacyApiKeysDao.get_api_keys correctly returns the expected key.

        Asserts:
            - Exactly one API key is returned for the service
            - The returned key's ID and name match the inserted key
        """
        keys = await LegacyApiKeysDao.get_api_keys(prepared_api_key.service_id)

        assert len(keys) == 1, 'prepared service should only have one api key'

        api_key = keys[0]

        for column in prepared_api_key._mapping.keys():
            expected = prepared_api_key._mapping[column]
            actual = api_key._mapping[column]
            assert actual == expected, f'{column} mismatch: expected {expected}, got {actual}'

    async def test_get_api_keys_should_return_empty_list(self) -> None:
        """API keys should not exist for non-existant service."""
        keys = await LegacyApiKeysDao.get_api_keys(uuid4())

        assert len(keys) == 0, 'keys should not exist'

    @pytest.mark.parametrize(
        ('raised_exception', 'expected_error'),
        [
            (DataError('stmt', 'params', Exception('orig')), NonRetryableError),
            (OperationalError('stmt', 'params', Exception('orig')), RetryableError),
            (InterfaceError('stmt', 'params', Exception('orig')), RetryableError),
            (TimeoutError(), RetryableError),
            (SQLAlchemyError('some generic error'), NonRetryableError),
        ],
    )
    async def test_get_api_keys_exception_handling(
        self,
        raised_exception: Exception,
        expected_error: type[Exception],
    ) -> None:
        """Test that get_api_keys raises the correct custom error when a specific SQLAlchemy exception occurs."""
        service_id = uuid4()

        # Patch the session context and simulate the exception during execution
        with patch('app.legacy.dao.api_keys_dao.get_read_session_with_context') as mock_session_ctx:
            mock_session = AsyncMock()
            mock_session.execute.side_effect = raised_exception
            mock_session_ctx.return_value.__aenter__.return_value = mock_session

            with pytest.raises(expected_error):
                await LegacyApiKeysDao.get_api_keys(service_id)


class TestApiKeyRecord:
    """Test ApiKeyRecord dataclass."""

    async def test_from_row_sets_fields(
        self,
        sample_api_key: Callable[..., Awaitable[Row[Any]]],
    ) -> None:
        """Ensure all fields from the row that exist on ApiKeyRecord match in the record instance."""
        api_key = await sample_api_key()
        record = ApiKeyRecord.from_row(api_key)

        # Excludes @property attributes, (e.g. secret which gets decrypted)
        dataclass_fields = record.__dataclass_fields__.keys()

        # excluding expiry_date as it undergoes tranformation (timezone) and tested elsewehere
        for column in api_key._mapping.keys():
            if column != 'expiry_date' and column in dataclass_fields:
                expected = api_key._mapping[column]
                actual = getattr(record, column)
                assert actual == expected, f"Mismatch on field '{column}': {actual!r} != {expected!r}"

    async def test_expiry_is_utc_if_naive(
        self,
        sample_api_key: Callable[..., Awaitable[Row[Any]]],
    ) -> None:
        """Ensure naive expiry_date is coerced to UTC."""
        api_key = await sample_api_key(expiry_date=datetime(2025, 1, 1, 12, 0, 0))

        record = ApiKeyRecord.from_row(api_key)

        assert record.expiry_date is not None
        assert record.expiry_date.tzinfo == timezone.utc

    async def test_expiry_preserves_timezone_if_aware(
        self,
        sample_api_key: Callable[..., Awaitable[Row[Any]]],
    ) -> None:
        """Ensure aware expiry_date is preserved as-is.

        Using America/New_York as test timezone since naive datetimes would be converted to UTC
        """
        aware_dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=ZoneInfo('America/New_York'))

        # Creating mocked Row[Any] to get around immutability
        # This simulates a row returned from the database with a datetime that still has a timezone
        # Row[Any] are otherwise read-only views
        api_key = await sample_api_key()
        row_dict = dict(api_key._mapping)
        row_dict['expiry_date'] = aware_dt
        record = ApiKeyRecord.from_row(Mock(**row_dict))

        assert record.expiry_date == aware_dt

    def test_secret_returns_decrypted_value(self) -> None:
        """Ensure the secret property decrypts the encrypted string."""
        secret = 'not_very_secret'

        record = ApiKeyRecord(
            id=uuid4(),
            _secret_encrypted=encode_and_sign(secret),
            service_id=uuid4(),
            expiry_date=None,
            revoked=False,
        )

        assert record.secret == secret

    def test_secret_returns_none_if_secret_is_none(self) -> None:
        """Ensure None is returned when _secret_encrypted is None."""
        record = ApiKeyRecord(
            id=uuid4(),
            _secret_encrypted=None,
            service_id=uuid4(),
            expiry_date=None,
            revoked=False,
        )
        assert record.secret is None

    def test_secret_returns_none_and_logs_error_if_decode_fails(self) -> None:
        """Ensure ValueError is propagated if decode fails."""
        record = ApiKeyRecord(
            id=uuid4(),
            _secret_encrypted='bad-data',
            service_id=uuid4(),
            expiry_date=None,
            revoked=False,
        )

        with patch('app.legacy.dao.api_keys_dao.logger.error') as mock_error:
            assert record.secret is None

        mock_error.assert_called_once_with(
            'Failed to decode API key secret for service_id: {} api_key_id: {}', record.service_id, record.id
        )
