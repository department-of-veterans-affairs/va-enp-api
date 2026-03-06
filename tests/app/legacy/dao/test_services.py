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
    """Test class for LegacyServiceDao methods."""

    async def test_get_happy_path(self, commit_service: Row[Any]) -> None:
        """Test the ability to get a service from the database.

        Args:
            commit_service (Row[Any]): Service that was commit to the database
        """
        service_row = await LegacyServiceDao.get(commit_service.id)
        assert service_row.id == commit_service.id

    async def test_get_non_existent_service(self) -> None:
        """Should raise NoResultFound when service does not exist in DB."""
        with pytest.raises(NonRetryableError):
            await LegacyServiceDao.get(uuid4())

    @pytest.mark.parametrize(
        ('caught_exception', 'raised_exception'),
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
    async def test_get_exception_handling(
        self,
        caught_exception: Exception,
        raised_exception: type[Exception],
    ) -> None:
        """Test that _get raises the correct custom error when a specific SQLAlchemy exception occurs.

        Args:
            caught_exception (Exception): The exception our code caught
            raised_exception (type[Exception]): The exception our code raised
        """
        service_id = uuid4()

        # Patch the session context and simulate the exception during execution
        with patch('app.legacy.dao.services_dao.get_read_session_with_context') as mock_session_ctx:
            mock_session = AsyncMock()
            mock_session.execute.side_effect = caught_exception
            mock_session_ctx.return_value.__aenter__.return_value = mock_session

            with pytest.raises(raised_exception):
                await LegacyServiceDao._get(service_id)
