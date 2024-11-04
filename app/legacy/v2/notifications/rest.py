"""All endpoints for the v2/notifications route."""

from datetime import datetime, timezone
from time import monotonic
from typing import Any, Callable, Coroutine, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from loguru import logger

from app.legacy.v2.notifications.route_schema import (
    V2NotificationPushRequest,
    V2NotificationPushResponse,
)
from app.legacy.v2.notifications.utils import get_arn_from_icn
from app.providers.provider_aws import ProviderAWS
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


class Template:
    """A mock representation of a Template model to simulate database retrieval."""

    def __init__(self, template_id: int, name: str) -> None:
        """Initialize a Template object.

        Args:
            template_id (int): The unique identifier of the template.
            name (str): The name of the template.

        """
        self.id = template_id
        self.name = name

    @staticmethod
    def build_message(personalization: dict[str, str]) -> str:
        """Build a personalized message.

        Args:
            personalization (dict[str, str]): A dictionary containing personalization data.

        Returns:
            str: A personalized message.

        """
        return f'Personalized message with {personalization}'

    @classmethod
    def get_template_by_id(cls, template_id: int) -> Optional['Template']:
        """Retrieve a template by its unique identifier.

        Args:
            template_id (int): The unique identifier of the template.

        Returns:
            Optional[Template]: A Template object if found, else None.

        """
        if template_id == 1:
            return cls(template_id=template_id, name='Sample Template')
        else:
            return None


@v2_notification_router.post('/', status_code=status.HTTP_201_CREATED)
async def create_notification(request: V2NotificationPushRequest) -> V2NotificationPushResponse:
    """Create a notification.

    Args:
    ----
        request (V2NotificationSingleRequest): The data necessary for the notification.

    Returns:
    -------
        V2NotificationPushResponse: The notification response data.

    Raises:
    ------
        HTTPException: If the template with the provided ID is not found.

    """
    # TODO - 1 Build ARN from ICN
    icn = request.recipient_identifier
    target_arn = await get_arn_from_icn(icn)

    # TODO - 2 Create Push Model with message, target_arn, and topic_arn
    # Query the database and get template with ID
    template_id = int(request.template_id)  # Convert template_id to int if required
    template = Template.get_template_by_id(template_id)

    if template is None:
        raise HTTPException(status_code=404, detail='Template not found')

    personalization = request.personalization or {}  # Ensure personalization is a dict
    message = template.build_message(personalization)
    push_model = PushModel(message=message, target_arn=target_arn, topic_arn=None)

    # TODO - 3 Pass Push Model to ProviderAWS.send_notification(Push Model)
    provider = ProviderAWS()
    reference_identifier = await provider.send_notification(model=push_model)

    # TODO - 4 Return 201
    response = V2NotificationPushResponse(
        id=uuid4(),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        sent_at=None,
        reference_identifier=reference_identifier,
    )
    return response
