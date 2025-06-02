"""Tests for templates DAO methods."""

from typing import Any, Awaitable, Callable
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
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NonRetryableError, RetryableError
from app.legacy.dao.templates_dao import LegacyTemplateDao


class TestLegacyTemplateDao:
    """Integration tests for LegacyTemplateDao methods using committed database records."""

    async def test_get_template(
        self,
        test_db_session: AsyncSession,
        sample_template: Callable[..., Awaitable[Row[Any]]],
    ) -> None:
        """Test that a template can be retrieved from the database by ID."""
        created_template = await sample_template()
        await test_db_session.commit()

        db_template = await LegacyTemplateDao.get_template(created_template.id)

        assert db_template is not None
        assert db_template.id == created_template.id

    async def test_get_template_raises_if_not_found(self) -> None:
        """Should raise NonRetryableError when template does not exist in DB."""
        non_existent_id = uuid4()

        with pytest.raises(NonRetryableError) as error:
            await LegacyTemplateDao.get_template(non_existent_id)

        assert 'Template lookup failed' in str(error.value.log_msg) or 'invalid or unexpected data' in str(
            error.value.log_msg
        )

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
    async def test_get_template_exception_handling(
        self,
        raised_exception: Exception,
        expected_error: type[Exception],
    ) -> None:
        """Test that get_template raises the correct custom error when a specific SQLAlchemy exception occurs."""
        template_id = uuid4()

        with patch('app.legacy.dao.templates_dao.get_read_session_with_context') as mock_session_ctx:
            mock_session = AsyncMock()
            mock_session.execute.side_effect = raised_exception
            mock_session_ctx.return_value.__aenter__.return_value = mock_session

            with pytest.raises(expected_error):
                await LegacyTemplateDao.get_template(template_id)
