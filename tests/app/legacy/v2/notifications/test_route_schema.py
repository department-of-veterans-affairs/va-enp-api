"""Test module for app/legacy/v2/notifications/route_schema.py.

The tests cover Pydantic models that have custom validation.
"""

from typing import Any, Awaitable, Callable
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy import Row

from app.constants import IdentifierType, NotificationType
from app.exceptions import NonRetryableError
from app.legacy.v2.notifications.route_schema import (
    RecipientIdentifierModel,
    V2PostEmailRequestModel,
    V2PostNotificationRequestModel,
    V2PostSmsRequestModel,
)

VALID_PHONE_NUMBER = '2025550123'
VALID_PHONE_NUMBER_E164 = '+12025550123'
INVALID_PHONE_NUMBER = '+5555555555'
VALID_ICN_VALUE = '1234567890V123456'

######################################################################
# Test POST e-mail schemas
######################################################################


@pytest.mark.parametrize(
    'data',
    [
        {'email_address': 'test@va.gov'},
        {'recipient_identifier': {'id_type': IdentifierType.ICN, 'id_value': VALID_ICN_VALUE}},
    ],
    ids=(
        'e-mail address',
        'recipient ID',
    ),
)
def test_v2_post_email_request_model_valid(data: dict[str, str | dict[str, str]]) -> None:
    """Valid data with an e-mail address should not raise ValidationError."""
    data['template_id'] = str(uuid4())
    assert isinstance(V2PostEmailRequestModel.model_validate(data), V2PostEmailRequestModel)


@pytest.mark.parametrize(
    'data',
    [
        {},
        {'email_address': 'test@va.gov', 'recipient_identifier': {'id_type': 'ICN', 'id_value': 'test'}},
    ],
    ids=(
        'neither e-mail address nor recipient ID',
        'e-mail address and recipient ID',
    ),
)
def test_v2_post_email_request_model_invalid(data: dict[str, str | dict[str, str]]) -> None:
    """Invalid data should raise ValidationError."""
    data['template_id'] = str(uuid4())

    with pytest.raises(ValidationError):
        V2PostEmailRequestModel.model_validate(data)


######################################################################
# Test POST SMS schemas
######################################################################


@pytest.mark.parametrize(
    ('phone_number', 'description'),
    [
        ('1800INVALID', 'Local non-numeric number'),
        ('+63919INVALID', 'International non-numeric number'),
    ],
)
def test_v2_post_sms_request_model_invalid_phone_number(phone_number: str | int, description: str) -> None:
    """Invalid non-numeric vanity phone numbers should raise ValidationError."""
    data = dict()
    data['phone_number'] = phone_number
    data['template_id'] = str(uuid4())

    with pytest.raises(ValidationError):
        V2PostSmsRequestModel.model_validate(data)


@pytest.mark.parametrize(
    'data',
    [
        {'phone_number': VALID_PHONE_NUMBER},
        {'recipient_identifier': {'id_type': IdentifierType.ICN, 'id_value': VALID_ICN_VALUE}},
        {
            'phone_number': VALID_PHONE_NUMBER,
            'recipient_identifier': {'id_type': IdentifierType.ICN, 'id_value': VALID_ICN_VALUE},
        },
    ],
    ids=(
        'phone number',
        'recipient ID',
        'phone number and recipient ID',
    ),
)
def test_v2_post_sms_request_model_valid(data: dict[str, str | dict[str, str]]) -> None:
    """Valid required data should not raise ValidationError."""
    data['sms_sender_id'] = str(uuid4())
    data['template_id'] = str(uuid4())

    request = V2PostSmsRequestModel.model_validate(data)
    assert isinstance(request, V2PostSmsRequestModel)

    if request.phone_number is not None:
        assert request.phone_number == VALID_PHONE_NUMBER_E164


@pytest.mark.parametrize(
    'data',
    [
        {},
        {'phone_number': INVALID_PHONE_NUMBER},
    ],
    ids=(
        'neither phone number nor recipient ID',
        'invalid us phone number',
    ),
)
def test_v2_post_sms_request_model_invalid(data: dict[str, str | dict[str, str]]) -> None:
    """Invalid data should raise ValidationError."""
    data['sms_sender_id'] = str(uuid4())
    data['template_id'] = str(uuid4())
    with pytest.raises(ValidationError):
        V2PostSmsRequestModel.model_validate(data)


class TestV2PostEmailRequestModel:
    """Test V2PostEmailRequestModel methods."""

    def test_simplest(self) -> None:
        """Test V2PostEmailRequestModel instantiation works."""
        V2PostEmailRequestModel(email_address='fake_email@va.gov', template_id=uuid4())

    async def test_get_reply_to(self, mocker: AsyncMock) -> None:
        """Test get_reply_to_tex returns a string.

        Args:
            mocker (AsyncMock): Mock object
        """
        mocker.patch(
            'app.legacy.v2.notifications.route_schema.LegacyTemplateDao.get',
            return_value=mocker.AsyncMock(),
            new_callable=AsyncMock,
        )
        model = V2PostEmailRequestModel(email_address='fake_email@va.gov', template_id=uuid4())
        assert isinstance(await model.get_reply_to_text(), str)

    def test_get_direct_contact_info(self) -> None:
        """Test get_direct_contact_info returns an email address."""
        email_address = 'fake_email@va.gov'
        model = V2PostEmailRequestModel(email_address=email_address, template_id=uuid4())
        assert model.get_direct_contact_info() == email_address

    def test_get_channel(self) -> None:
        """Test get_channel returns the correct channel."""
        model = V2PostEmailRequestModel(email_address='fake_email@va.gov', template_id=uuid4())
        assert model.get_channel() == NotificationType.EMAIL


class TestV2PostSmsRequestModel:
    """Test V2PostSmsRequestModel methods."""

    def test_simplest_phone_number(self) -> None:
        """Test V2PostSmsRequestModel instantiation works."""
        V2PostSmsRequestModel(phone_number='+18005550101', template_id=uuid4())

    async def test_get_reply_to_with_sender(
        self,
        sample_service: Callable[..., Awaitable[Row[Any]]],
        sample_service_sms_sender: Callable[..., Awaitable[Row[Any]]],
        mocker: AsyncMock,
    ) -> None:
        """Test get_reply_to_text returns the correct sms_sender.

        Args:
            sample_service (Callable[..., Awaitable[Row[Any]]]): Service
            sample_service_sms_sender (Callable[..., Awaitable[Row[Any]]]): ServiceSmsSender
            mocker (AsyncMock): Mock object
        """
        service_sms_sender = await sample_service_sms_sender((await sample_service()).id)
        mocker.patch(
            'app.legacy.v2.notifications.route_schema.LegacyServiceSmsSenderDao.get', return_value=service_sms_sender
        )
        mocker.patch('app.legacy.v2.notifications.route_schema.context')
        model = V2PostSmsRequestModel(
            phone_number='+18005550101', template_id=uuid4(), sms_sender_id=service_sms_sender.id
        )
        assert (await model.get_reply_to_text()) == service_sms_sender.sms_sender

    async def test_get_reply_to_no_sender(
        self,
        sample_service: Callable[..., Awaitable[Row[Any]]],
        sample_service_sms_sender: Callable[..., Awaitable[Row[Any]]],
        mocker: AsyncMock,
    ) -> None:
        """Test get_reply_to_text returns the correct sms_sender.

        Args:
            sample_service (Callable[..., Awaitable[Row[Any]]]): Service
            sample_service_sms_sender (Callable[..., Awaitable[Row[Any]]]): ServiceSmsSender
            mocker (AsyncMock): Mock object
        """
        service_sms_sender = await sample_service_sms_sender((await sample_service()).id)
        mocker.patch(
            'app.legacy.v2.notifications.route_schema.LegacyServiceSmsSenderDao.get_service_default',
            return_value=service_sms_sender,
        )
        mocker.patch('app.legacy.v2.notifications.route_schema.context')
        model = V2PostSmsRequestModel(phone_number='+18005550101', template_id=uuid4())
        assert (await model.get_reply_to_text()) == service_sms_sender.sms_sender

    async def test_get_reply_to_exception(self, mocker: AsyncMock) -> None:
        """Test get_reply_to_text raises the exception correctly.

        Args:
            mocker (AsyncMock): Mock object
        """
        mock_context = mocker.patch('app.legacy.v2.notifications.route_schema.context')
        service_id = uuid4()
        sms_sender_id = uuid4()
        mock_context.__getitem__.return_value = service_id
        mocker.patch(
            'app.legacy.v2.notifications.route_schema.LegacyServiceSmsSenderDao.get', side_effect=NonRetryableError
        )

        model = V2PostSmsRequestModel(phone_number='+18005550101', template_id=uuid4(), sms_sender_id=sms_sender_id)
        with pytest.raises(HTTPException) as exc_info:
            await model.get_reply_to_text()
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert (
            exc_info.value.detail
            == f'sms_sender_id {sms_sender_id} does not exist in database for service id {service_id}'
        )

    def test_get_direct_contact_info(self) -> None:
        """Test get_direct_contact_info returns a phone number."""
        phone_number = '+18005550101'
        model = V2PostSmsRequestModel(phone_number=phone_number, template_id=uuid4())
        assert model.get_direct_contact_info() == phone_number

    def test_get_channel(self) -> None:
        """Test get_channel returns the correct channel."""
        model = V2PostSmsRequestModel(phone_number='+18005550101', template_id=uuid4())
        assert model.get_channel() == NotificationType.SMS


class TestV2PostNotificationRequestModel:
    """Test V2PostNotificationRequestModel functionality."""

    def test_simplest_recipient_identifier(self) -> None:
        """Test V2PostNotificationRequestModel instantiation works with RecipientIdentifierModel."""
        recipient = RecipientIdentifierModel(id_type=IdentifierType.VA_PROFILE_ID, id_value='12345')
        V2PostNotificationRequestModel(recipient_identifier=recipient, template_id=uuid4())

    async def test_get_reply_to(self, mocker: AsyncMock) -> None:
        """Test get_reply_to_text is not implemented.

        Args:
            mocker (AsyncMock): Mock object
        """
        mocker.patch('app.legacy.v2.notifications.route_schema.LegacyTemplateDao.get', return_value=mocker.AsyncMock())
        recipient = RecipientIdentifierModel(id_type=IdentifierType.VA_PROFILE_ID, id_value='12345')
        model = V2PostNotificationRequestModel(recipient_identifier=recipient, template_id=uuid4())
        with pytest.raises(NotImplementedError):
            await model.get_reply_to_text()

    def test_get_direct_contact_info(self) -> None:
        """Test get_direct_contact_info is not implemented."""
        recipient = RecipientIdentifierModel(id_type=IdentifierType.VA_PROFILE_ID, id_value='12345')
        model = V2PostNotificationRequestModel(recipient_identifier=recipient, template_id=uuid4())
        with pytest.raises(NotImplementedError):
            model.get_direct_contact_info()

    def test_get_channel(self) -> None:
        """Test get_channel is not implemented."""
        recipient = RecipientIdentifierModel(id_type=IdentifierType.VA_PROFILE_ID, id_value='12345')
        model = V2PostNotificationRequestModel(recipient_identifier=recipient, template_id=uuid4())
        with pytest.raises(NotImplementedError):
            model.get_channel()
