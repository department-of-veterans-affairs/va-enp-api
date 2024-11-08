"""All endpoints for the v2/notifications route."""

import json
from time import monotonic
from typing import Any, Callable, Coroutine

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from loguru import logger

from app.dao.notifications_dao import dao_create_notification
from app.db.models import Notification, Template
from app.legacy.v2.notifications.route_schema import (
    V2NotificationPushRequest,
    V2NotificationPushResponse,
)
from app.legacy.v2.notifications.utils import send_push_notification_helper, validate_template
from app.v3.notifications.rest import RESPONSE_400, RESPONSE_404, RESPONSE_500


class NotificationV2Route(APIRoute):
    """Custom route class for V2 notifications."""

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        """Override default handler.

        Returns:
            Callable: the route handler

        """
        original_route_handler = super().get_route_handler()

        async def custom_route_handler(request: Request) -> Response:
            """Add timing and exception handling to requests passed in.

            Args:
                request (Request): the request

            Returns:
                Response: the response

            Raises:
                HTTPException: a 500 error if an exception occurs

            """
            status_code = None
            try:
                start = monotonic()
                resp = await original_route_handler(request)
                status_code = resp.status_code
                return resp
            except RequestValidationError as exc:
                logger.warning(
                    'Request: {} Failed validation: {}',
                    request,
                    exc,
                )
                raise HTTPException(status.HTTP_400_BAD_REQUEST, f'{RESPONSE_400} - {exc}')
            except HTTPException:
                raise
            except Exception as exc:
                logger.exception('{}: {}', RESPONSE_500, type(exc).__name__)
                raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, RESPONSE_500)
            finally:
                logger.info('{} {} {} {}s', request.method, request.url, status_code, f'{(monotonic() - start):6f}')

        return custom_route_handler


v2_notification_router = APIRouter(
    prefix='/v2/notifications',
    tags=['v2 Notification Endpoints'],
    responses={404: {'description': RESPONSE_404}},
    route_class=NotificationV2Route,
)


@v2_notification_router.post('/push', status_code=status.HTTP_201_CREATED)
async def create_push_notification(
    request_data: V2NotificationPushRequest,
    request: Request,
    background_tasks: BackgroundTasks,
) -> V2NotificationPushResponse:
    """Create a push notification.

    Args:
    ----
        request_data (V2NotificationSingleRequest): The data necessary for the notification.
        request (Request): The FastAPI request object.
        background_tasks (BackgroundTasks): The FastAPI background tasks object.

    Raises:
    ------
        HTTPException: If the template with the given template_id is not found.

    Returns:
    -------
        V2NotificationPushResponse: The notification response data.

    """
    icn = request_data.recipient_identifier.id_value
    template_id = str(request_data.template_id)
    personalisation = request_data.personalisation

    logger.info('Creating notification with recipent_identifier {} and template_id {}.', icn, template_id)

    try:
        template: Template = await validate_template(template_id)
    except Exception:
        # we could use a more specific exception here
        logger.warning('Template not found with ID {}', template_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Undeliverable - Validation failed. Template not found with template_id {template_id}',
        )

    await dao_create_notification(Notification(personalization=json.dumps(personalisation)))

    background_tasks.add_task(
        send_push_notification_helper, personalisation, icn, template, request.app.state.providers['aws']
    )

    logger.info('Successful notification with recipient_identifer {} and template_id {}.', icn, template_id)
    return V2NotificationPushResponse()
