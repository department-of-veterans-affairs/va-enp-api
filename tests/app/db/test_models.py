"""Tests the creation of year-based partitions for the `Notification` table."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.db.models import Notification, create_notification_year_partition


class TestCreateNotificationYearPartition:
    """Test class for `create_notification_year_partition`."""

    def setup_method(self) -> None:
        """Initialize mocks for each test."""
        self.mock_connection: MagicMock = MagicMock()

    def test_create_notification_year_partition_success(self, mocker: MagicMock) -> None:
        """Test successful creation of year-based partitions."""
        mock_datetime = mocker.patch('app.db.models.datetime')
        mock_datetime.now.return_value = datetime(2025, 1, 1, tzinfo=timezone.utc)
        mock_logger = mocker.patch('app.db.models.logger')

        create_notification_year_partition(Notification, connection=self.mock_connection)

        sql_calls = [str(call[0][0]) for call in self.mock_connection.execute.call_args_list]

        assert self.mock_connection.execute.call_count == 3

        for sql in sql_calls:
            for year in [2024, 2025, 2026]:
                if f'notifications_{year}' in sql:
                    assert 'PARTITION OF notifications' in sql
                    assert f"'{year}-01-01'" in sql
                    assert f"'{year + 1}-01-01'" in sql
                    assert 'created_at' in sql

        mock_logger.info.assert_has_calls(
            [
                mocker.call('Partition for year {} ensured.', 2024),
                mocker.call('Partition for year {} ensured.', 2025),
                mocker.call('Partition for year {} ensured.', 2026),
            ],
            any_order=True,
        )

    def test_create_notification_year_partition_failure(self, mocker: MagicMock) -> None:
        """Test handling of SQL execution failure."""
        mock_exception = SQLAlchemyError('Database error')
        self.mock_connection.execute.side_effect = mock_exception
        mock_logger = mocker.patch('app.db.models.logger')

        with pytest.raises(SQLAlchemyError):
            create_notification_year_partition(Notification, connection=self.mock_connection)

        mock_logger.critical.assert_called_once_with('Error creating partition for year {}: {}', 2024, mock_exception)
