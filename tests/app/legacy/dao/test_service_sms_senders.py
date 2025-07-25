"""Tests for service_sms_sender DAO methods."""

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
from app.legacy.dao.service_sms_sender_dao import LegacyServiceSmsSenderDao


class TestLegacyServiceSmsSenderDaoGet:
    """Test class for LegacyServiceSmsSenderDao get methods."""

    async def test_get_happy_path(self, commit_service_sms_sender: Row[Any]) -> None:
        """Test the ability to get a service_sms_sender from the database.

        Args:
            commit_service_sms_sender (Row[Any]): ServiceSmsSender that was committed to the database
        """
        sms_sender_row = await LegacyServiceSmsSenderDao.get(id=commit_service_sms_sender.id)
        assert sms_sender_row.id == commit_service_sms_sender.id

    async def test_get_non_existent_service_sms_sender(self) -> None:
        """Should raise NonRetryableError when service_sms_sender does not exist in DB."""
        with pytest.raises(NonRetryableError):
            await LegacyServiceSmsSenderDao.get(id=uuid4())

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
        """Test that get raises the correct custom error when a specific SQLAlchemy exception occurs.

        Args:
            caught_exception (Exception): The exception our code caught
            raised_exception (type[Exception]): The exception we expect to be raised
        """
        # Patch the session context and simulate the exception during execution
        with patch('app.legacy.dao.service_sms_sender_dao.get_read_session_with_context') as mock_session_ctx:
            mock_session = AsyncMock()
            mock_session.execute.side_effect = caught_exception
            mock_session_ctx.return_value.__aenter__.return_value = mock_session

            with pytest.raises(raised_exception):
                await LegacyServiceSmsSenderDao._get(id=uuid4())


class TestLegacyServiceSmsSenderDaoGetServiceDefault:
    """Test class for LegacyServiceSmsSenderDao get_service_default methods."""

    async def test_get_happy_path(self, commit_service_sms_sender: Row[Any]) -> None:
        """Test the ability to get a service_sms_sender from the database.

        Args:
            commit_service_sms_sender (Row[Any]): ServiceSmsSender that was committed to the database
        """
        sms_sender_row = await LegacyServiceSmsSenderDao.get_service_default(
            service_id=commit_service_sms_sender.service_id
        )
        assert sms_sender_row.id == commit_service_sms_sender.id
        assert sms_sender_row.is_default, 'Expected the sms sender to be the default'

    async def test_get_non_existent_service_sms_sender(self) -> None:
        """Should raise NonRetryableError when service_sms_sender does not exist in DB."""
        with pytest.raises(NonRetryableError):
            await LegacyServiceSmsSenderDao.get_service_default(service_id=uuid4())

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
        """Test that get raises the correct custom error when a specific SQLAlchemy exception occurs.

        Args:
            caught_exception (Exception): The exception our code caught
            raised_exception (type[Exception]): The exception we expect to be raised
        """
        # Patch the session context and simulate the exception during execution
        with patch('app.legacy.dao.service_sms_sender_dao.get_read_session_with_context') as mock_session_ctx:
            mock_session = AsyncMock()
            mock_session.execute.side_effect = caught_exception
            mock_session_ctx.return_value.__aenter__.return_value = mock_session

            with pytest.raises(raised_exception):
                await LegacyServiceSmsSenderDao._get_service_default(service_id=uuid4())
