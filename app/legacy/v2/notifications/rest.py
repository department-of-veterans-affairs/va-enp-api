"""All endpoints for the v2/notifications route."""

from datetime import datetime, timezone
from time import monotonic
from typing import Any, Callable, Coroutine, Union
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from loguru import logger

from app.db.models import Template
from app.legacy.v2.notifications.route_schema import (
    V2NotificationPushRequest,
    V2NotificationPushResponse,
)
from app.legacy.v2.notifications.utils import get_arn_from_icn
from app.providers.provider_aws import ProviderAWS
from app.providers.provider_base import ProviderNonRetryableError, ProviderRetryableError
from app.providers.provider_schemas import PushModel
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
                status_code = 400
                logger.warning(
                    'Request: {} Failed validation: {}',
                    request,
                    exc,
                )
                raise HTTPException(400, f'{RESPONSE_400} - {exc}')
            except Exception as exc:
                status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
                logger.exception('{}: {}', RESPONSE_500, type(exc).__name__)
                raise HTTPException(status_code, RESPONSE_500)
            finally:
                logger.info('{} {} {} {}s', request.method, request.url, status_code, f'{(monotonic() - start):6f}')

        return custom_route_handler


v2_notification_router = APIRouter(
    prefix='/v2/notifications',
    tags=['v2 Notification Endpoints'],
    responses={404: {'description': RESPONSE_404}},
    route_class=NotificationV2Route,
)


@v2_notification_router.post('/', status_code=status.HTTP_201_CREATED, response_model=None)
async def create_notification(request: V2NotificationPushRequest) -> Union[V2NotificationPushResponse, Response]:
    """Create a notification.

    Args:
    ----
        request (V2NotificationSingleRequest): The data necessary for the notification.

    Returns:
    -------
        V2NotificationPushResponse: The notification response data.


    """
    icn = request.recipient_identifier
    template_id = int(request.template_id)

    logger.info('Creating notification with recipent_identifier {} and template_id {}.', icn, template_id)

    target_arn = await get_arn_from_icn(icn)
    template = Template.get_template_by_id(template_id)

    if template is None:
        logger.info('Template with ID {} not found', template_id)
        return Response(
            status_code=status.HTTP_400_BAD_REQUEST, content=f'Template with template_id {template_id} not found.'
        )

    personalization = request.personalization or {}
    message = template.build_message(personalization)
    push_model = PushModel(message=message, target_arn=target_arn, topic_arn=None)

    try:
        provider = ProviderAWS()
        reference_identifier = await provider.send_notification(model=push_model)
    except (ProviderRetryableError, ProviderNonRetryableError) as error:
        logger.critical('Failed to send notification for recipient_identifier {}: {}', icn, str(error))
        return Response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content='Internal error. Failed to create notification.'
        )

    response = V2NotificationPushResponse(
        id=uuid4(),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        sent_at=None,
        reference_identifier=reference_identifier,
    )

    logger.info('Successfully notification with reccipent_identifier {} and template_id {}.', icn, template_id)
    return response
