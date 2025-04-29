"""Test module for app/legacy/v2/notifications/handlers.py."""

from abc import ABC  # Explicitly import to test coverage
from uuid import UUID

import pytest

from app.constants import IdentifierType, QueueNames
from app.legacy.v2.notifications.resolvers import (
    DirectSmsTaskResolver,
    IdentifierSmsTaskResolver,
    SmsTaskResolver,
)


class TestSmsTaskResolver:
    """Test the SmsTaskResolver class."""

    def test_abstractmethod(self) -> None:
        """Test that SmsTaskResolver is an abstract class with abstract method."""
        # We can't instantiate SmsTaskResolver directly
        with pytest.raises(TypeError):
            SmsTaskResolver()  # type: ignore

        # Explicitly verify ABC and abstractmethod are used correctly
        assert issubclass(SmsTaskResolver, ABC)
        assert hasattr(SmsTaskResolver.get_tasks, '__isabstractmethod__')


class TestDirectSmsTaskResolver:
    """Test the DirectSmsTaskResolver class."""

    def test_init(self) -> None:
        """Test initialization with phone number."""
        phone_number = '+18005550101'
        resolver = DirectSmsTaskResolver(phone_number)
        assert resolver.phone_number == phone_number

    def test_get_tasks(self) -> None:
        """Test get_tasks returns expected task."""
        phone_number = '+18005550101'
        notification_id = UUID('a71400e3-b2f8-4bd1-91c0-27f9ca7106a1')
        resolver = DirectSmsTaskResolver(phone_number)
        tasks = resolver.get_tasks(notification_id)

        # Verify a single task is returned with correct queue name and task name
        assert len(tasks) == 1
        task = tasks[0]
        assert task == (QueueNames.SEND_SMS, ('deliver_sms', notification_id))


class TestIdentifierSmsTaskResolver:
    """Test the IdentifierSmsTaskResolver class."""

    def test_init(self) -> None:
        """Test initialization with recipient identifier type and value."""
        id_type = IdentifierType.ICN
        id_value = '1234567890V123456'
        resolver = IdentifierSmsTaskResolver(id_type=id_type, id_value=id_value)
        assert resolver.id_type == id_type
        assert resolver.id_value == id_value

    def test_get_tasks_with_icn(self) -> None:
        """Test get_tasks with ICN identifier type returns expected tasks."""
        id_type = IdentifierType.ICN
        id_value = '1234567890V123456'
        notification_id = UUID('a71400e3-b2f8-4bd1-91c0-27f9ca7106a1')
        resolver = IdentifierSmsTaskResolver(id_type=id_type, id_value=id_value)
        tasks = resolver.get_tasks(notification_id)

        # Verify three tasks are returned with correct queue names and task details
        assert len(tasks) == 3

        # Check each task has the expected queue name and parameters
        expected_tasks = [
            (QueueNames.LOOKUP_VA_PROFILE_ID, ('lookup_va_profile_id', notification_id)),
            (QueueNames.LOOKUP_CONTACT_INFO, ('lookup_contact_info', notification_id)),
            (QueueNames.SEND_SMS, ('deliver_sms', notification_id)),
        ]

        assert tasks == expected_tasks

    def test_get_tasks_with_va_profile_id(self) -> None:
        """Test get_tasks with VA_PROFILE_ID identifier type returns expected tasks."""
        id_type = IdentifierType.VA_PROFILE_ID
        id_value = '123456789'
        notification_id = UUID('a71400e3-b2f8-4bd1-91c0-27f9ca7106a1')
        resolver = IdentifierSmsTaskResolver(id_type=id_type, id_value=id_value)
        tasks = resolver.get_tasks(notification_id)

        # Verify two tasks are returned with correct queue names and task details
        assert len(tasks) == 2

        # Check each task has the expected queue name and parameters
        expected_tasks = [
            (QueueNames.LOOKUP_CONTACT_INFO, ('lookup_contact_info', notification_id)),
            (QueueNames.SEND_SMS, ('deliver_sms', notification_id)),
        ]

        assert tasks == expected_tasks
