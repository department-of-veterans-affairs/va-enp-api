"""Tests for services DAO methods."""

from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.engine import Row
from sqlalchemy.exc import (
    DataError,
    InterfaceError,
    MultipleResultsFound,
    NoResultFound,
    OperationalError,
    SQLAlchemyError,
    TimeoutError,
)

from app.exceptions import NonRetryableError, RetryableError
from app.legacy.dao.services_dao import LegacyServiceDao


class TestLegacyServiceDao:
    """Integration tests for LegacyServiceDao methods using committed database records.

    These tests validate the behavior of service-related DAO operations against
    the actual database schema and logic, rather than mocking or in-memory objects.
    """

    async def test_get_service(self, prepared_service: Row[Any]) -> None:
        """Test that a service can be retrieved from the database by ID.

        Given a committed service record (via the prepared_service fixture),
        this test verifies that LegacyServiceDao.get_service_by_id returns
        the correct row from the database.

        Asserts:
            - The retrieved service ID matches the inserted service ID.
        """
        service = await LegacyServiceDao.get(prepared_service.id)

        for column in prepared_service._mapping.keys():
            expected = prepared_service._mapping[column]
            actual = service._mapping[column]
            assert actual == expected, f'{column} mismatch: expected {expected}, got {actual}'

    async def test_get_service_raises_if_not_found(self) -> None:
        """Should raise NoResultFound when service does not exist in DB."""
        with pytest.raises(NonRetryableError):
            await LegacyServiceDao.get(uuid4())

    @pytest.mark.parametrize(
        ('raised_exception', 'expected_error'),
        [
            (NoResultFound(), NonRetryableError),
            (MultipleResultsFound(), NonRetryableError),
            (DataError('stmt', 'params', Exception('orig')), NonRetryableError),
            (OperationalError('stmt', 'params', Exception('orig')), RetryableError),
            (InterfaceError('stmt', 'params', Exception('orig')), RetryableError),
            (TimeoutError(), RetryableError),
            (SQLAlchemyError('some generic error'), NonRetryableError),
        ],
    )
    async def test_get_service_exception_handling(
        self,
        raised_exception: Exception,
        expected_error: type[Exception],
    ) -> None:
        """Test that get_service raises the correct custom error when a specific SQLAlchemy exception occurs."""
        service_id = uuid4()

        # Patch the session context and simulate the exception during execution
        with patch('app.legacy.dao.services_dao.get_read_session_with_context') as mock_session_ctx:
            mock_session = AsyncMock()
            mock_session.execute.side_effect = raised_exception
            mock_session_ctx.return_value.__aenter__.return_value = mock_session

            with pytest.raises(expected_error):
                await LegacyServiceDao._get(service_id)
