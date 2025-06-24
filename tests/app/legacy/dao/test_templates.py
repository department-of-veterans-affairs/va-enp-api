"""Tests for templates DAO methods."""

from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import Row
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
from app.legacy.dao.templates_dao import LegacyTemplateDao


class TestLegacyTemplateDaoGet:
    """Test class for LegacyTemplateDao Get by ID method."""

    async def test_get_happy_path(self, commit_template: Row[Any]) -> None:
        """Test the ability to get a template from the database.

        Args:
            commit_template (Row[Any]): Template that was commit to the database
        """
        template_row = await LegacyTemplateDao.get(commit_template.id)
        assert template_row.id == commit_template.id

    async def test_get_non_existent_template(self) -> None:
        """Should raise NoResultFound when template does not exist in DB."""
        with pytest.raises(NonRetryableError):
            await LegacyTemplateDao.get(uuid4())

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
        template_id = uuid4()

        # Patch the session context and simulate the exception during execution
        with patch('app.legacy.dao.templates_dao.get_read_session_with_context') as mock_session_ctx:
            mock_session = AsyncMock()
            mock_session.execute.side_effect = caught_exception
            mock_session_ctx.return_value.__aenter__.return_value = mock_session

            with pytest.raises(raised_exception):
                await LegacyTemplateDao._get(template_id)


class TestLegacyTemplateDaoGetByIdAndServiceId:
    """Test class for LegacyTemplateDao methods."""

    async def test_get_happy_path(self, commit_template: Row[Any]) -> None:
        """Test the ability to get a template from the database.

        Args:
            commit_template (Row[Any]): Template that was commit to the database
        """
        template_row = await LegacyTemplateDao.get_by_id_and_service_id(commit_template.id, commit_template.service_id)
        assert template_row.id == commit_template.id

    async def test_get_non_existent_template(self) -> None:
        """Should raise NoResultFound when template does not exist in DB."""
        template_id = uuid4()
        service_id = uuid4()

        with pytest.raises(NonRetryableError):
            await LegacyTemplateDao.get_by_id_and_service_id(template_id, service_id)

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
        template_id = uuid4()
        service_id = uuid4()

        # Patch the session context and simulate the exception during execution
        with patch('app.legacy.dao.templates_dao.get_read_session_with_context') as mock_session_ctx:
            mock_session = AsyncMock()
            mock_session.execute.side_effect = caught_exception
            mock_session_ctx.return_value.__aenter__.return_value = mock_session

            with pytest.raises(raised_exception):
                await LegacyTemplateDao._get_by_id_and_service_id(template_id, service_id)
