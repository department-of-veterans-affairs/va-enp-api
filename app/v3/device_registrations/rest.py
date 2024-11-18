"""All endpoints for the v3/notifications route."""

from time import monotonic
from typing import Any, Callable, Coroutine

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import Response
from fastapi.routing import APIRoute
from loguru import logger

from app.providers.provider_schemas import DeviceRegistrationModel
from app.v3.device_registrations.route_schema import DeviceRegistrationSingleRequest, DeviceRegistrationSingleResponse
from app.v3.device_registrations.tasks import register_device_with_vaprofile

RESPONSE_400 = 'Request body failed validation'
RESPONSE_404 = 'Not found'
RESPONSE_500 = 'Unhandled VA Notify exception'


class DeviceRegistrationRoute(APIRoute):
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


api_router = APIRouter(
    prefix='/v3/device-registrations',
    tags=['v3 Device Registration Endpoints'],
    responses={404: {'description': RESPONSE_404}},
    route_class=DeviceRegistrationRoute,
)


@api_router.post('/', status_code=status.HTTP_201_CREATED)
async def create_device_registration(
    request: DeviceRegistrationSingleRequest,
    fastapi_request: Request,
    background_tasks: BackgroundTasks,
) -> DeviceRegistrationSingleResponse:
    """Create a device registration, from a mobile app.

    Args:
        request (DeviceRegistrationSingleRequest): Data for the request
        fastapi_request (Request): The FastAP:I request object
        background_tasks (BackgroundTasks): The FastAPI background tasks object

    Returns:
        Upon success, a DeviceRegistrationSingleResponse object is returned.

    """
    logger.debug('Received device registration request: {}', request)

    provider = fastapi_request.app.state.providers.get('aws')
    logger.debug('Loaded provider: {}', provider)

    device_registration_model = DeviceRegistrationModel(
        device_name=request.device_name,
        token=request.device_token,
        platform_application_name=request.app_name,
    )
    response = await provider.register_device(device_registration_model)

    # The endpoint_sid is the last part of the ARN, split by "/"
    endpoint_sid = response.split('/')[-1]

    # Add the task to the background tasks queue
    background_tasks.add_task(
        register_device_with_vaprofile,
        endpoint_sid,
        request.device_name,
        request.os_name,
    )

    return DeviceRegistrationSingleResponse(
        endpoint_sid=endpoint_sid,
    )
