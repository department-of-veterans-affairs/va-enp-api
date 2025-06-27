"""Test module for app/legacy/v2/notifications/rest.py."""

from collections.abc import AsyncGenerator, Generator
from typing import Any, Awaitable, Callable, Coroutine
from unittest.mock import AsyncMock, Mock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import BackgroundTasks, status
from fastapi.encoders import jsonable_encoder
from pydantic import UUID4
from sqlalchemy import Row, delete

from app.clients.redis_client import RedisClientManager
from app.constants import IdentifierType, MobileAppType, NotificationType
from app.db.db_init import get_write_session_with_context, metadata_legacy
from app.legacy.dao.notifications_dao import LegacyNotificationDao
from app.legacy.dao.service_sms_sender_dao import LegacyServiceSmsSenderDao
from app.legacy.v2.notifications.resolvers import (
    DirectSmsTaskResolver,
    IdentifierSmsTaskResolver,
)
from app.legacy.v2.notifications.rest import _sms_post
from app.legacy.v2.notifications.route_schema import (
    PersonalisationFileObject,
    RecipientIdentifierModel,
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
        # Bypass auth and rate limiters, this is testing request data
        mocker.patch('app.auth.verify_service_token')

        # Mock the context to provide the required values for rate limiting
        mock_context = {
            'request_id': 'test-request-id',
            'service_id': 'test-service-id',
            'api_key_id': 'test-api-key-id',
        }
        mocker.patch('app.limits.context', mock_context)

        # Mock Redis client to allow rate limiting to pass (return True for rate limit checks)
        mock_redis = Mock()
        mock_redis.consume_rate_limit_token = AsyncMock(return_value=True)

        # Mock the Redis client manager on the app
        mocker.patch.object(client.app.enp_state, 'redis_client_manager', mock_redis)

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
            template_id='36fb0730-6259-4da1-8a80-c8de22ad4246',
            recipient_identifier=V2PostPushRequestModel.ICNRecipientIdentifierModel(
                id_type=IdentifierType.ICN,
                id_value='12345',
            ),
            personalisation={'name': 'John'},
        )

        # Bypass auth and rate limiters, this is testing request data
        mocker.patch('app.auth.verify_service_token')

        # Mock the context to provide the required values for rate limiting
        mock_context = {
            'request_id': 'test-request-id-2',
            'service_id': 'test-service-id-2',
            'api_key_id': 'test-api-key-id-2',
        }
        mocker.patch('app.limits.context', mock_context)

        # Mock Redis client to allow rate limiting to pass (return True for rate limit checks)
        mock_redis = Mock()
        mock_redis.consume_rate_limit_token = AsyncMock(return_value=True)

        # Mock the Redis client manager on the app
        mocker.patch.object(client.app.enp_state, 'redis_client_manager', mock_redis)

        response = client.post(_push_path, json=request.model_dump())

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json() == {'result': 'success'} == V2PostPushResponseModel().model_dump()


@patch.object(BackgroundTasks, 'add_task')
class TestSmsPostHandler:
    """Test the v2 SMS notifications router."""

    sms_route = '/legacy/v2/notifications/sms'

    @pytest.fixture
    async def prepare_database(
        self,
        sample_api_key: Callable[..., Awaitable[Row[Any]]],
        sample_service: Callable[..., Awaitable[Row[Any]]],
        sample_service_sms_sender: Callable[..., Awaitable[Row[Any]]],
        sample_template: Callable[..., Awaitable[Row[Any]]],
        sample_user: Callable[..., Awaitable[Row[Any]]],
    ) -> AsyncGenerator[Callable[[], Coroutine[Any, Any, dict[str, Row[Any]]]], None]:
        """Prepare the database for SMS requests and tear down.

        Args:
            sample_api_key (Callable[..., Awaitable[Row[Any]]]): ApiKey
            sample_service (Callable[..., Awaitable[Row[Any]]]): Service
            sample_service_sms_sender (Callable[..., Awaitable[Row[Any]]]): ServiceSmsSender
            sample_template (Callable[..., Awaitable[Row[Any]]]): Template
            sample_user (Callable[..., Awaitable[Row[Any]]]): User

        Yields:
            Iterator[AsyncGenerator[Callable[[], Coroutine[Any, Any, dict[str, Row[Any]]]], None]]: Callable for rows
        """
        # Needs to be persisted in a collection
        ids = {}

        async def _wrapper() -> dict[str, Row[Any]]:
            async with get_write_session_with_context() as session:
                user = await sample_user(session)
                service = await sample_service(session, created_by_id=user.id)
                await sample_service_sms_sender(service.id, session, is_default=True)  # Service default, bury it
                service_sms_sender = await sample_service_sms_sender(service.id, session, is_default=False)
                template = await sample_template(session, service_id=service.id, created_by_id=user.id)
                api_key = await sample_api_key(session, service_id=service.id)
                await session.commit()
            ids['user'] = user.id
            ids['service'] = service.id
            ids['template'] = template.id
            ids['api_key'] = api_key.id
            return {
                'user': user,
                'service': service,
                'template': template,
                'api_key': api_key,
                'service_sms_sender': service_sms_sender,
            }

        yield _wrapper

        # Teardown
        legacy_api_keys = metadata_legacy.tables['api_keys']
        legacy_services = metadata_legacy.tables['services']
        legacy_service_sms_senders = metadata_legacy.tables['service_sms_senders']
        legacy_templates = metadata_legacy.tables['templates']
        legacy_templates_hist = metadata_legacy.tables['templates_history']
        legacy_users = metadata_legacy.tables['users']

        async with get_write_session_with_context() as session:
            # delete both service_sms_sender entries - Uses the service_id to delete instead of it's id
            sender_delete_stmt = delete(legacy_service_sms_senders).where(
                legacy_service_sms_senders.c.service_id == ids['service']
            )
            await session.execute(sender_delete_stmt)
            # delete the template history
            th_delete_stmt = delete(legacy_templates_hist).where(legacy_templates_hist.c.id == ids['template'])
            await session.execute(th_delete_stmt)
            # delete the template
            template_delete_stmt = delete(legacy_templates).where(legacy_templates.c.id == ids['template'])
            await session.execute(template_delete_stmt)
            # delete the api key
            key_delete_stmt = delete(legacy_api_keys).where(legacy_api_keys.c.id == ids['api_key'])
            await session.execute(key_delete_stmt)
            # delte the service
            service_delete_stmt = delete(legacy_services).where(legacy_services.c.id == ids['service'])
            await session.execute(service_delete_stmt)
            # delete the user
            user_delete_stmt = delete(legacy_users).where(legacy_users.c.id == ids['user'])
            await session.execute(user_delete_stmt)
            await session.commit()

    @pytest.fixture
    def build_headers(
        self,
    ) -> Generator[Callable[[UUID, UUID], dict[str, str]], None]:
        """Generator to build headers.

        Use of this fixture is associated with notifications added to the database.

        Args:
            sample_api_key (Callable[..., Awaitable[Row[Any]]]): Sample key generator

        Yields:
            Iterator[Generator[Callable[[str | None], Coroutine[Any, Any, dict[str, str]]], None]]: Generator that builds header data and tears down any created notifications
        """

        def _wrapper(api_key_id: UUID4, service_id: UUID4) -> dict[str, str]:
            # Based on sample_api_key's secret being secret-id
            secret_str = f'secret-{api_key_id}'
            return generate_headers(secret_str, str(service_id))

        yield _wrapper
        ...

    @pytest.fixture
    def path_request(
        self,
    ) -> Generator[
        Callable[
            [
                UUID,
                str | None,
                UUID | None,
                str | None,
                RecipientIdentifierModel | None,
                dict[str, str | int | float | list[str | int | float] | PersonalisationFileObject] | None,
            ],
            dict[str, object],
        ]
    ]:
        """Generator to build request data.

        Yields:
            Generator[ Callable[ [ str | None, UUID4 | None, str | None, RecipientIdentifierModel | None, dict[str, str | int | float | list[str | int | float] | PersonalisationFileObject] | None, ], dict[str, object], ], None, ]: Request data
        """

        def _wrapper(
            template_id: UUID4,
            reference: str | None = None,
            sms_sender_id: UUID4 | None = None,
            phone_number: str | None = None,
            recipient_identifier: RecipientIdentifierModel | None = None,
            personalization: dict[str, str | int | float | list[str | int | float] | PersonalisationFileObject]
            | None = None,
        ) -> dict[str, object]:
            # Default to the simplest. Template requires personalization
            request_data: V2PostSmsRequestModel
            if phone_number:
                request_data = V2PostSmsRequestModel(
                    phone_number=ValidatedPhoneNumber(phone_number),
                    template_id=template_id,
                    personalisation=personalization,
                )
            else:
                request_data = V2PostSmsRequestModel(
                    recipient_identifier=recipient_identifier,
                    template_id=template_id,
                    personalisation=personalization,
                )
            if reference is not None:
                request_data.reference = reference
            if sms_sender_id is not None:
                request_data.sms_sender_id = sms_sender_id
            data: dict[str, object] = jsonable_encoder(request_data)
            return data

        yield _wrapper
        # mypy and pytest expect a yield. Ruff expects something after yield, but that is not necessary.
        ...

    async def test_with_phone_number_returns_201(
        self,
        mock_background_task: AsyncMock,
        client: ENPTestClient,
        prepare_database: Callable[[], Coroutine[Any, Any, dict[str, Row[Any]]]],
        path_request: Callable[..., dict[str, object]],
        build_headers: Callable[[UUID, UUID], dict[str, str]],
    ) -> None:
        """Test sms notification route returns 201 with valid template."""
        db_data = await prepare_database()
        request = path_request(db_data['template'].id, phone_number='+18005550101')
        headers = build_headers(db_data['api_key'].id, db_data['service'].id)
        try:
            response = client.post(self.sms_route, json=request, headers=headers)
            assert response.status_code == status.HTTP_201_CREATED
        finally:
            await LegacyNotificationDao.delete_notification(response.json()['id'])

    async def test_with_recipient_id_returns_201(
        self,
        mock_background_task: AsyncMock,
        client: ENPTestClient,
        prepare_database: Callable[[], Coroutine[Any, Any, dict[str, Row[Any]]]],
        path_request: Callable[..., dict[str, object]],
        build_headers: Callable[[UUID, UUID], dict[str, str]],
    ) -> None:
        """Test sms notification route returns 201 with valid template."""
        recipient = RecipientIdentifierModel(id_type=IdentifierType.VA_PROFILE_ID, id_value='12345')
        db_data = await prepare_database()
        request = path_request(db_data['template'].id, recipient_identifier=recipient)
        headers = build_headers(db_data['api_key'].id, db_data['service'].id)
        try:
            response = client.post(self.sms_route, json=request, headers=headers)
            assert response.status_code == status.HTTP_201_CREATED
        finally:
            await LegacyNotificationDao.delete_notification(response.json()['id'])

    @pytest.mark.parametrize('reference', [None, str(uuid4()), ''])
    async def test_reference(
        self,
        mock_background_task: AsyncMock,
        client: ENPTestClient,
        prepare_database: Callable[[], Coroutine[Any, Any, dict[str, Row[Any]]]],
        path_request: Callable[..., dict[str, object]],
        build_headers: Callable[[UUID, UUID], dict[str, str]],
        reference: UUID4 | None,
    ) -> None:
        """Test sms notification route returns 201 with valid template."""
        db_data = await prepare_database()
        request = path_request(db_data['template'].id, phone_number='+18005550101', reference=reference)
        headers = build_headers(db_data['api_key'].id, db_data['service'].id)
        try:
            response = client.post(self.sms_route, json=request, headers=headers)
            assert response.status_code == status.HTTP_201_CREATED
            resp_json = response.json()
            assert resp_json['reference'] == reference if reference is not None else 'null'
        finally:
            await LegacyNotificationDao.delete_notification(resp_json['id'])

    async def test_sms_sender_id_in_request(
        self,
        mock_background_task: AsyncMock,
        client: ENPTestClient,
        prepare_database: Callable[[], Coroutine[Any, Any, dict[str, Row[Any]]]],
        path_request: Callable[..., dict[str, object]],
        build_headers: Callable[[UUID, UUID], dict[str, str]],
    ) -> None:
        """Test sms notification route returns 201 with valid template."""
        db_data = await prepare_database()
        request = path_request(
            template_id=db_data['template'].id,
            phone_number='+18005550101',
            sms_sender_id=db_data['service_sms_sender'].id,
        )
        headers = build_headers(db_data['api_key'].id, db_data['service'].id)
        try:
            response = client.post(self.sms_route, json=request, headers=headers)
            resp_json = response.json()
            assert response.status_code == status.HTTP_201_CREATED

            # Validate the passed-in sms_sender_id was used
            notification = await LegacyNotificationDao.get(resp_json['id'])
            assert notification.reply_to_text == db_data['service_sms_sender'].sms_sender
        finally:
            await LegacyNotificationDao.delete_notification(resp_json['id'])

    async def test_sms_sender_id_default(
        self,
        mock_background_task: AsyncMock,
        client: ENPTestClient,
        prepare_database: Callable[[], Coroutine[Any, Any, dict[str, Row[Any]]]],
        path_request: Callable[..., dict[str, object]],
        build_headers: Callable[[UUID, UUID], dict[str, str]],
    ) -> None:
        """Test sms notification route returns 201 with valid template."""
        db_data = await prepare_database()
        request = path_request(template_id=db_data['template'].id, phone_number='+18005550101')
        headers = build_headers(db_data['api_key'].id, db_data['service'].id)
        try:
            response = client.post(self.sms_route, json=request, headers=headers)
            resp_json = response.json()
            assert response.status_code == status.HTTP_201_CREATED

            # Validate the correct sms sender was used
            notification = await LegacyNotificationDao.get(resp_json['id'])
            service_sms_sender = await LegacyServiceSmsSenderDao.get_service_default(db_data['service'].id)
            assert notification.reply_to_text == service_sms_sender.sms_sender
        finally:
            await LegacyNotificationDao.delete_notification(resp_json['id'])

    async def test_rate_limited_returns_429(
        self,
        mock_background_task: AsyncMock,
        mocker: AsyncMock,
        client: ENPTestClient,
        prepare_database: Callable[[], Coroutine[Any, Any, dict[str, Row[Any]]]],
        path_request: Callable[..., dict[str, object]],
        build_headers: Callable[[UUID, UUID], dict[str, str]],
    ) -> None:
        """Test sms notification route returns 429 when rate limited."""
        db_data = await prepare_database()
        request = path_request(db_data['template'].id, phone_number='+18005550101')
        headers = build_headers(db_data['api_key'].id, db_data['service'].id)

        # mock redis client manager to rate limit
        redis_mock = Mock(spec=RedisClientManager)
        redis_mock.consume_rate_limit_token = AsyncMock(return_value=False)
        client.app.enp_state.redis_client_manager = redis_mock

        response = client.post(
            self.sms_route,
            json=request,
            headers=headers,
        )
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS


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
        # Bypass auth and rate limiters, this is testing request data
        mocker.patch('app.auth.verify_service_token')

        # Mock the context to provide the required values for rate limiting
        mock_context = {
            'request_id': 'test-request-id-3',
            'service_id': 'test-service-id-3',
            'api_key_id': 'test-api-key-id-3',
        }
        mocker.patch('app.limits.context', mock_context)

        # Mock Redis client to allow rate limiting to pass (return True for rate limit checks)
        mock_redis = Mock()
        mock_redis.consume_rate_limit_token = AsyncMock(return_value=True)

        # Mock the Redis client manager on the app
        mocker.patch.object(client.app.enp_state, 'redis_client_manager', mock_redis)

        response = client.post(route)

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@patch('app.legacy.v2.notifications.rest.context')
@patch.object(BackgroundTasks, 'add_task')
class TestSmsPost:
    """Test the _sms_post method."""

    @pytest.fixture
    def mock_template_validations(self, mocker: AsyncMock) -> UUID4:
        """Fixture to mock a template.

        Args:
            mocker (AsyncMock): Mock object

        Returns:
            Any: The mocked template
        """
        template_id = uuid4()
        mock_template = mocker.AsyncMock()
        mock_template.id = template_id
        mock_template.template_type = NotificationType.SMS
        mock_template.archived = False
        mock_template.service_id = uuid4()
        mocker.patch('app.legacy.v2.notifications.rest.validate_template', return_value=mock_template)
        mocker.patch('app.legacy.v2.notifications.rest.validate_template_personalisation')
        return template_id

    async def test_happy_path_direct(
        self,
        mock_background_task: AsyncMock,
        mock_context: AsyncMock,
        mocker: AsyncMock,
        mock_template_validations: AsyncMock,
    ) -> None:
        """Test _sms_post works with a recipient identifier."""
        mock_context.data = {'request_id': uuid4(), 'service_id': uuid4()}
        mocker.patch('app.legacy.v2.notifications.rest.create_notification')

        request = V2PostSmsRequestModel(phone_number='+18005550101', template_id=mock_template_validations)
        mock_resolver = mocker.AsyncMock(spec=DirectSmsTaskResolver)
        await _sms_post(request, mock_resolver, mock_background_task)

    async def test_happy_path_recipient(
        self,
        mock_background_task: AsyncMock,
        mock_context: AsyncMock,
        mocker: AsyncMock,
        mock_template_validations: AsyncMock,
    ) -> None:
        """Test _sms_post works with a recipient identifier."""
        mock_context.data = {'request_id': uuid4(), 'service_id': uuid4()}
        mocker.patch('app.legacy.v2.notifications.rest.create_notification')
        mock_resolver = mocker.AsyncMock(spec=IdentifierSmsTaskResolver)
        recipient = RecipientIdentifierModel(id_type=IdentifierType.VA_PROFILE_ID, id_value='12345')
        request = V2PostSmsRequestModel(recipient_identifier=recipient, template_id=mock_template_validations)
        await _sms_post(request, mock_resolver, mock_background_task)
