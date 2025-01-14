"""Test module for app/legacy/v2/notifications/rest.py."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import BackgroundTasks, status
from fastapi.encoders import jsonable_encoder

from app.constants import IdentifierType, MobileAppType, USNumberType
from app.db.models import Template
from app.legacy.v2.notifications.route_schema import (
    V2PostPushRequestModel,
    V2PostPushResponseModel,
    V2PostSmsRequestModel,
)
from tests.conftest import ENPTestClient

_push_path = '/legacy/v2/notifications/push'


@patch.object(BackgroundTasks, 'add_task')
@patch('app.legacy.v2.notifications.rest.dao_create_notification')
@patch('app.legacy.v2.notifications.rest.validate_template')
class TestPushRouter:
    """Test the v2 push notifications router."""

    async def test_router_returns_400_with_invalid_request_data(
        self,
        mock_validate_template: AsyncMock,
        mock_dao_create_notification: AsyncMock,
        mock_background_task: AsyncMock,
        client: ENPTestClient,
    ) -> None:
        """Test route can return 400.

        Args:
            mock_validate_template (AsyncMock): Mock call to validate_template
            mock_dao_create_notification (AsyncMock): Mock call to create notification in the database
            mock_background_task (AsyncMock): Mock call to add a background task
            client (ENPTestClient): Custom FastAPI client fixture

        """
        invalid_request = {
            'mobile_app': 'fake_app',
            'template_id': 'not_a_uuid',
            'recipient_identifier': {
                'id_type': 'not_ICN',
                'id_value': r'¯\_(ツ)_/¯',
            },
            'personalization': 'not_a_dict',
        }

        response = client.post(_push_path, json=invalid_request)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    async def test_router_returns_500_when_other_exception_thrown(
        self,
        mock_validate_template: AsyncMock,
        mock_dao_create_notification: AsyncMock,
        mock_background_task: AsyncMock,
        client: ENPTestClient,
    ) -> None:
        """Test route can return 500.

        Args:
            mock_validate_template (AsyncMock): Mock call to validate_template
            mock_dao_create_notification (AsyncMock): Mock call to create notification in the database
            mock_background_task (AsyncMock): Mock call to add a background task
            client (ENPTestClient): Custom FastAPI client fixture

        """
        mock_validate_template.return_value = Template(name='test_template')
        mock_dao_create_notification.side_effect = Exception()

        request = V2PostPushRequestModel(
            mobile_app=MobileAppType.VA_FLAGSHIP_APP,
            template_id='d5b6e67c-8e2a-11ee-8b8e-0242ac120002',
            recipient_identifier=V2PostPushRequestModel.ICNRecipientIdentifierModel(
                id_type=IdentifierType.ICN,
                id_value='12345',
            ),
            personalisation={'name': 'John'},
        )

        response = client.post(_push_path, json=request.model_dump())

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


@patch.object(BackgroundTasks, 'add_task')
@patch('app.legacy.v2.notifications.rest.dao_create_notification')
@patch('app.legacy.v2.notifications.rest.validate_template')
class TestPush:
    """Test POST /legacy/v2/notifications/push."""

    async def test_post_push_returns_201(
        self,
        mock_validate_template: AsyncMock,
        mock_dao_create_notification: AsyncMock,
        mock_background_task: AsyncMock,
        client: ENPTestClient,
    ) -> None:
        """Test route can return 201.

        Args:
            mock_validate_template (AsyncMock): Mock call to validate_template
            mock_dao_create_notification (AsyncMock): Mock call to create notification in the database
            mock_background_task (AsyncMock): Mock call to add a background task
            client (ENPTestClient): Custom FastAPI client fixture

        """
        mock_validate_template.return_value = Template(name='test_template')

        request = V2PostPushRequestModel(
            mobile_app=MobileAppType.VA_FLAGSHIP_APP,
            template_id='d5b6e67c-8e2a-11ee-8b8e-0242ac120002',
            recipient_identifier=V2PostPushRequestModel.ICNRecipientIdentifierModel(
                id_type=IdentifierType.ICN,
                id_value='12345',
            ),
            personalisation={'name': 'John'},
        )

        response = client.post(_push_path, json=request.model_dump())

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json() == {'result': 'success'} == V2PostPushResponseModel().model_dump()

    async def test_post_push_returns_400_when_unable_to_validate_template(
        self,
        mock_validate_template: AsyncMock,
        mock_dao_create_notification: AsyncMock,
        mock_background_task: AsyncMock,
        client: ENPTestClient,
    ) -> None:
        """Test route returns 400 when there is an exception thrown trying to validate the template.

        Args:
            mock_validate_template (AsyncMock): Mock call to validate_template
            mock_dao_create_notification (AsyncMock): Mock call to create notification in the database
            mock_background_task (AsyncMock): Mock call to add a background task
            client (ENPTestClient): Custom FastAPI client fixture

        """
        mock_validate_template.side_effect = Exception()

        request = V2PostPushRequestModel(
            mobile_app=MobileAppType.VA_FLAGSHIP_APP,
            template_id='d5b6e67c-8e2a-11ee-8b8e-0242ac120002',
            recipient_identifier=V2PostPushRequestModel.ICNRecipientIdentifierModel(
                id_type=IdentifierType.ICN,
                id_value='12345',
            ),
            personalisation={'name': 'John'},
        )

        response = client.post(_push_path, json=request.model_dump())

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestNotificationRouter:
    """Test the v2 notifications router."""

    routes = (
        '/legacy/v2/notifications/sms',
        '/v2/notifications/sms',
    )

    @pytest.mark.parametrize('route', routes)
    async def test_happy_path(
        self,
        client: ENPTestClient,
        route: str,
    ) -> None:
        """Test route can return 201.

        Args:
            client (ENPTestClient): Custom FastAPI client fixture
            route (str): Route to test

        """
        template_id = uuid4()
        sms_sender_id = uuid4()

        request = V2PostSmsRequestModel(
            reference='test',
            template_id=template_id,
            phone_number=USNumberType('+18005550101'),
            sms_sender_id=sms_sender_id,
        )
        payload = jsonable_encoder(request)
        response = client.post(route, json=payload)

        assert response.status_code == status.HTTP_201_CREATED

    @pytest.mark.parametrize('route', routes)
    async def test_router_returns_400_with_invalid_request_data(
        self,
        client: ENPTestClient,
        route: str,
    ) -> None:
        """Test route can return 400.

        Args:
            client (ENPTestClient): Custom FastAPI client fixture
            route (str): Route to test

        """
        response = client.post(route)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
