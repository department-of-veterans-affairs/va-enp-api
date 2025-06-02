"""Test module for app/legacy/v2/notifications/rest.py."""

from collections.abc import AsyncGenerator, Generator
from typing import Any, Awaitable, Callable, Coroutine
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import BackgroundTasks, status
from fastapi.encoders import jsonable_encoder
from pydantic import UUID4
from sqlalchemy import Row, delete

from app.constants import IdentifierType, MobileAppType
from app.db.db_init import get_write_session_with_context, metadata_legacy
from app.legacy.dao.notifications_dao import LegacyNotificationDao
from app.legacy.v2.notifications.resolvers import (
    DirectSmsTaskResolver,
    IdentifierSmsTaskResolver,
)
from app.legacy.v2.notifications.rest import _sms_post
from app.legacy.v2.notifications.route_schema import (
    PersonalisationFileObject,
    RecipientIdentifierModel,
    V2PostNotificationRequestModel,
    V2PostPushRequestModel,
    V2PostPushResponseModel,
    V2PostSmsRequestModel,
    ValidatedPhoneNumber,
)
from tests.conftest import ENPTestClient, generate_headers

_push_path = '/legacy/v2/notifications/push'


class TestPushRouter:
    """Test the v2 push notifications router."""

    async def test_router_returns_400_with_invalid_request_data(
        self,
        mock_background_task: AsyncMock,
        mocker: AsyncMock,
        client: ENPTestClient,
    ) -> None:
        """Test route can return 400.

        Args:
            mock_background_task (AsyncMock): Mock call to add a background task
            mocker (AsyncMock): Mock object
            client (ENPTestClient): Custom FastAPI client fixture

        """
        invalid_request = {
            'mobile_app': 'fake_app',
            'template_id': 'not_a_uuid',
            'recipient_identifier': {
                'id_type': 'not_ICN',
                'id_value': r'¯\_(ツ)_/¯',
            },
            'personalisation': 'not_a_dict',
        }
        # Bypass auth, this is testing request data
        mocker.patch('app.auth.verify_service_token')
        response = client.post(_push_path, json=invalid_request)

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestPush:
    """Test POST /legacy/v2/notifications/push."""

    async def test_post_push_returns_201(
        self,
        mock_background_task: AsyncMock,
        mocker: AsyncMock,
        client: ENPTestClient,
    ) -> None:
        """Test route can return 201.

        Args:
            mock_background_task (AsyncMock): Mock call to add a background task
            mocker (AsyncMock): Mock object
            client (ENPTestClient): Custom FastAPI client fixture

        """
        request = V2PostPushRequestModel(
            mobile_app=MobileAppType.VA_FLAGSHIP_APP,
            template_id='d5b6e67c-8e2a-11ee-8b8e-0242ac120002',
            recipient_identifier=V2PostPushRequestModel.ICNRecipientIdentifierModel(
                id_type=IdentifierType.ICN,
                id_value='12345',
            ),
            personalisation={'name': 'John'},
        )

        # Bypass auth, this is testing request data
        mocker.patch('app.auth.verify_service_token')
        response = client.post(_push_path, json=request.model_dump())

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json() == {'result': 'success'} == V2PostPushResponseModel().model_dump()


@patch.object(BackgroundTasks, 'add_task')
class TestSmsPostHandler:
    """Test the v2 SMS notifications router."""

    sms_route = '/legacy/v2/notifications/sms'

    @pytest.fixture
    async def build_headers(
        self,
        sample_api_key: Callable[..., Awaitable[Row[Any]]],
    ) -> AsyncGenerator[Callable[[str | None], Coroutine[Any, Any, dict[str, str]]], None]:
        """Generator to build headers.

        Use of this fixture is associated with notifications added to the database.

        Args:
            sample_api_key (Callable[..., Awaitable[Row[Any]]]): Sample key generator

        Yields:
            Iterator[AsyncGenerator[Callable[[str | None], Coroutine[Any, Any, dict[str, str]]], None]]: Generator that builds header data and tears down any created notifications
        """
        key_ids: list[UUID4] = []

        async def _wrapper(secret: str | None = None) -> dict[str, str]:
            secret_str = secret or f'secret-{uuid4()}'
            # VA Notify seeded service
            service_id = UUID('d6aa2c68-a2d9-4437-ab19-3ae8eb202553')
            async with get_write_session_with_context() as session:
                key_ids.append((await sample_api_key(session, service_id=service_id, secret=secret_str)).id)
                await session.commit()
            return generate_headers(secret_str, str(service_id))

        yield _wrapper

        # Teardown
        legacy_notifications = metadata_legacy.tables['notifications']
        legacy_api_keys = metadata_legacy.tables['api_keys']
        notification_stmt = delete(legacy_notifications).where(legacy_notifications.c.api_key_id == key_ids[0])
        key_stmt = delete(legacy_api_keys).where(legacy_api_keys.c.id == key_ids[0])
        async with get_write_session_with_context() as session:
            await session.execute(notification_stmt)
            await session.execute(key_stmt)
            await session.commit()

    @pytest.fixture
    def path_request(
        self,
    ) -> Generator[
        Callable[
            [
                str | None,
                UUID4 | None,
                str | None,
                RecipientIdentifierModel | None,
                dict[str, str | int | float | list[str | int | float] | PersonalisationFileObject] | None,
            ],
            dict[str, object],
        ],
        None,
    ]:
        """Generator to build request data.

        Yields:
            Generator[ Callable[ [ str | None, UUID4 | None, str | None, RecipientIdentifierModel | None, dict[str, str | int | float | list[str | int | float] | PersonalisationFileObject] | None, ], dict[str, object], ], None, ]: Request data
        """

        def _wrapper(
            reference: str | None = None,
            sms_sender_id: UUID4 | None = None,
            phone_number: str | None = None,
            recipient_identifier: RecipientIdentifierModel | None = None,
            personalization: dict[str, str | int | float | list[str | int | float] | PersonalisationFileObject]
            | None = None,
        ) -> dict[str, object]:
            # Default to the simplest. Template requires personalization
            request_data: V2PostSmsRequestModel | V2PostNotificationRequestModel
            if phone_number:
                request_data = V2PostSmsRequestModel(
                    phone_number=ValidatedPhoneNumber(phone_number),
                    template_id=UUID('36fb0730-6259-4da1-8a80-c8de22ad4246'),  # Seeded in migration 0025
                    personalisation=personalization or {'verify_code': '12345'},
                )
            else:
                request_data = V2PostNotificationRequestModel(
                    recipient_identifier=recipient_identifier,
                    template_id=UUID('36fb0730-6259-4da1-8a80-c8de22ad4246'),  # Seeded in migration 0025
                    personalisation=personalization or {'verify_code': '12345'},
                )
            # TODO: KWM Implement tests that use these before up for PR
            # if reference is not None:
            #     request_data.reference = reference
            # if sms_sender_id is not None:
            #     request_data.sms_sender_id = sms_sender_id
            data: dict[str, object] = jsonable_encoder(request_data)
            return data

        yield _wrapper
        # mypy and pytest expect a yield. Ruff expects something after yield, but that is not necessary.
        ...

    async def test_with_phone_number_returns_201(
        self,
        mock_background_task: AsyncMock,
        client: ENPTestClient,
        path_request: Callable[..., dict[str, object]],
        build_headers: Callable[..., Coroutine[Any, Any, dict[str, str]]],
    ) -> None:
        """Test sms notification route returns 201 with valid template."""
        try:
            response = client.post(
                self.sms_route,
                json=path_request(phone_number='+18005550101'),
                headers=await build_headers(),
            )
            assert response.status_code == status.HTTP_201_CREATED
        finally:
            await LegacyNotificationDao.delete_notification(response.json()['id'])

    async def test_with_recipient_id_returns_201(
        self,
        mock_background_task: AsyncMock,
        client: ENPTestClient,
        path_request: Callable[..., dict[str, object]],
        build_headers: Callable[..., Coroutine[Any, Any, dict[str, str]]],
    ) -> None:
        """Test sms notification route returns 201 with valid template."""
        recipient = RecipientIdentifierModel(id_type=IdentifierType.VA_PROFILE_ID, id_value='12345')
        try:
            response = client.post(
                self.sms_route,
                json=path_request(recipient_identifier=recipient),
                headers=await build_headers(),
            )
            assert response.status_code == status.HTTP_201_CREATED
        finally:
            await LegacyNotificationDao.delete_notification(response.json()['id'])


class TestSmsValidation:
    """Test validation of the sms route(s)."""

    routes = (
        '/legacy/v2/notifications/sms',
        '/v2/notifications/sms',
    )

    @pytest.mark.parametrize('route', routes)
    async def test_router_returns_400_with_invalid_request_data(
        self,
        client: ENPTestClient,
        route: str,
        mocker: AsyncMock,
    ) -> None:
        """Responds with 400 when no data sent to the route.

        Args:
            client (ENPTestClient): Test client
            route (str): Route under test
            mocker (AsyncMock): Mock object
        """
        # Bypass auth, this is testing request data
        mocker.patch('app.auth.verify_service_token')
        response = client.post(route)

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@patch('app.legacy.v2.notifications.rest.context')
@patch.object(BackgroundTasks, 'add_task')
class TestSmsPost:
    """Test the _sms_post method."""

    @pytest.fixture
    def mock_template_get_id(self, mocker: AsyncMock) -> UUID4:
        """Fixture to mock a template.

        Args:
            mocker (AsyncMock): Mock object

        Returns:
            Any: The mocked template
        """
        template_id = uuid4()
        mock_template = mocker.AsyncMock()
        mock_template.id = template_id
        mocker.patch('app.legacy.v2.notifications.rest.validate_template', return_value=mock_template)
        return template_id

    async def test_happy_path_direct(
        self,
        mock_background_task: AsyncMock,
        mock_context: AsyncMock,
        mocker: AsyncMock,
        mock_template_get_id: AsyncMock,
    ) -> None:
        """Test _sms_post works with a recipient identifier.

        Args:
            mock_background_task (AsyncMock): Mock BackgroundTasks
            mock_context (AsyncMock): Mock starlette context
            mocker (AsyncMock): Mock object
            mock_template_get_id (AsyncMock): Fixture to mock template setup
        """
        mock_context.data = {'request_id': uuid4(), 'service_id': uuid4()}
        mocker.patch('app.legacy.v2.notifications.rest.create_notification')
        request = V2PostSmsRequestModel(phone_number='+18005550101', template_id=mock_template_get_id)
        mock_resolveer = mocker.AsyncMock(spec=DirectSmsTaskResolver)
        await _sms_post(request, mock_resolveer, mock_background_task)

    async def test_happy_path_recipient(
        self,
        mock_background_task: AsyncMock,
        mock_context: AsyncMock,
        mocker: AsyncMock,
        mock_template_get_id: AsyncMock,
    ) -> None:
        """Test _sms_post works with a recipient identifier.

        Args:
            mock_background_task (AsyncMock): Mock BackgroundTasks
            mock_context (AsyncMock): Mock starlette context
            mocker (AsyncMock): Mock object
            mock_template_get_id (AsyncMock): Fixture to mock template setup
        """
        mock_context.data = {'request_id': uuid4(), 'service_id': uuid4()}
        mocker.patch('app.legacy.v2.notifications.rest.create_notification')
        mock_resolveer = mocker.AsyncMock(spec=IdentifierSmsTaskResolver)
        recipient = RecipientIdentifierModel(id_type=IdentifierType.VA_PROFILE_ID, id_value='12345')
        request = V2PostSmsRequestModel(recipient_identifier=recipient, template_id=mock_template_get_id)
        await _sms_post(request, mock_resolveer, mock_background_task)
