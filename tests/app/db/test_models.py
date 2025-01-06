"""Tests the creation of year-based partitions for the `Notification` table."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql import text

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

        sql_2024 = text(
            """CREATE TABLE IF NOT EXISTS notifications_2024
            PARTITION OF notifications
            FOR VALUES FROM ('2024-01-01')
            TO ('2025-01-01');

            CREATE INDEX IF NOT EXISTS idx_notifications_2024gi_created_at
            ON notifications_2024 (created_at);""".strip()
        )

        sql_2025 = text(
            """CREATE TABLE IF NOT EXISTS notifications_2025
            PARTITION OF notifications
            FOR VALUES FROM ('2025-01-01')
            TO ('2026-01-01');

            CREATE INDEX IF NOT EXISTS idx_notifications_2025_created_at
            ON notifications_2025 (created_at);""".strip()
        )

        expected_sql_calls = [mocker.call(sql_2024), mocker.call(sql_2025)]

        self.mock_connection.execute.assert_has_calls(expected_sql_calls, any_order=True)
        assert self.mock_connection.execute.call_count == 2

        mock_logger.info.assert_has_calls(
            [mocker.call('Partition for year {} ensured.', 2024), mocker.call('Partition for year {} ensured.', 2025)],
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
