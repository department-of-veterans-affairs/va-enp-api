"""All endpoints for the v3/device-registrations route."""

from fastapi import APIRouter, BackgroundTasks, Request, status

from app.clients.va_profile import register_device_with_vaprofile
from app.logging.logging_config import logger
from app.providers.provider_schemas import DeviceRegistrationModel
from app.routers import TimedAPIRoute
from app.v3.device_registrations.route_schema import DeviceRegistrationRequest, DeviceRegistrationResponse

api_router = APIRouter(
    prefix='/device-registrations',
    route_class=TimedAPIRoute,
)


@api_router.post('/', status_code=status.HTTP_201_CREATED)
async def create_device_registration(
    request: DeviceRegistrationRequest,
    fastapi_request: Request,
    background_tasks: BackgroundTasks,
) -> DeviceRegistrationResponse:
    """Create a device registration.

    Args:
        request (DeviceRegistrationSingleRequest): Data for the request
        fastapi_request (Request): The FastAPI request object
        background_tasks (BackgroundTasks): The FastAPI background tasks object

    Returns:
        Upon success, a DeviceRegistrationSingleResponse object is returned.

    """
    logger.debug('Received device registration request: {}', request)

    provider = fastapi_request.app.enp_state.providers['aws']
    logger.debug('Loaded provider: {}', provider)

    device_registration_model = DeviceRegistrationModel(
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
        request.app_name,
        request.device_token,
    )

    return DeviceRegistrationResponse(
        endpoint_sid=endpoint_sid,
    )
