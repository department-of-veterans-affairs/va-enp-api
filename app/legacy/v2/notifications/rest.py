"""All endpoints for the v2/notifications route."""

from datetime import datetime, timezone
from time import monotonic
from typing import Any, Callable, Coroutine
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from loguru import logger

from app.legacy.v2.notifications.route_schema import V2NotificationSingleRequest, V2NotificationSingleResponse
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


@v2_notification_router.post('/', status_code=status.HTTP_201_CREATED)
async def create_notification(request: V2NotificationSingleRequest) -> V2NotificationSingleResponse:
    """Create a notification.

    Args:
    ----
        request (V2NotificationSingleRequest): the data necessary for the notification

    Returns:
    -------
        dict[str, str]: the notification response data

    """
    # request =
    # {'mobile_app':VA_FLAGSHIP_APP,
    #  'template_id':'2',
    #  'recipient_identifier':'99999',
    #  'personalisation':{'name': 'John'},
    # }

    # TODO - 1 Get ARN for AWS using ICN
    # Note - Do not implement call to VeText, instead return NotImplemented error
    # TODO - 2 Create Push Model with message, target_arn, and topic_arn
    # TODO - 3 Pass Push Model to ProviderAWS.send_notification(Push Model)
    # TODO - 4 Return 201

    response = V2NotificationSingleResponse(
        id=uuid4(),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        sent_at=None,
        to=request.to,
    )
    return response
