"""All endpoints for the v3/notifications route."""

from datetime import datetime, timezone
from time import monotonic
from typing import Any, Callable, Coroutine
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import Response
from fastapi.routing import APIRoute
from loguru import logger
from pydantic import UUID4

from app.v3.notifications.route_schema import NotificationSingleRequest, NotificationSingleResponse

RESPONSE_400 = 'Request body failed validation'
RESPONSE_404 = 'Not found'
RESPONSE_500 = 'Unhandled VA Notify exception'


class NotificationRoute(APIRoute):
    """Exception and logging handling."""

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        """Override default handler.

        Returns
        -------
            Callable: the route handler

        """
        original_route_handler = super().get_route_handler()

        async def custom_route_handler(request: Request) -> Response:
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
            except HTTPException:
                raise
            except Exception as exc:
                status_code = 500
                logger.exception('{}: {}', RESPONSE_500, type(exc).__name__)
                raise HTTPException(status_code, RESPONSE_500)
            finally:
                logger.info(
                    '{} {} {} {}',
                    request.method,
                    request.url,
                    status_code,
                    f'{(monotonic() - start):6f}',
                )

        return custom_route_handler


# https://fastapi.tiangolo.com/reference/apirouter/
notification_router = APIRouter(
    prefix='/v3/notifications',
    tags=['v3 Notification Endpoints'],
    responses={404: {'description': RESPONSE_404}},
    route_class=NotificationRoute,
)


@notification_router.get('/{notification_id}', status_code=status.HTTP_200_OK)
async def get_notification(notification_id: UUID4) -> UUID4:
    """Get a notification.

    Args:
    ----
        notification_id (UUID4): The notification to get

    Returns:
    -------
        UUID4: The notification object

    """
    return notification_id


@notification_router.post('/', status_code=status.HTTP_202_ACCEPTED)
async def create_notification(request: NotificationSingleRequest) -> NotificationSingleResponse:
    """Return app status.

    Args:
    ----
        request (NotificationSingleRequest): Data for the request

    Returns:
    -------
        UUID4: The notification object

    """
    response = NotificationSingleResponse(
        id=uuid4(),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        to=request.to,
    )
    return response


def test_cov_helper() -> None:
    """Function used to help cover the router in testing until we have real route functions here."""
    ...


@notification_router.post('/not-implemented', status_code=status.HTTP_200_OK)
async def cov_route() -> None:
    """Cover the conditions of the custom router while testing."""
    test_cov_helper()

    return None
