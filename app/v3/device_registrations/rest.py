"""All endpoints for the v3/notifications route."""

from time import monotonic
from typing import Any, Callable, Coroutine
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import Response
from fastapi.routing import APIRoute
from loguru import logger

from app.providers.provider_aws import ProviderAWS

from .route_schema import DeviceRegistrationSingleRequest, DeviceRegistrationSingleResponse

RESPONSE_400 = 'Request body failed validation'
RESPONSE_404 = 'Not found'
RESPONSE_500 = 'Unhandled VA Notify exception'


def get_aws_provider() -> ProviderAWS:
    """Get the AWS provider from the providers dictionary.

    Returns:
    -------
        ProviderAWS: the AWS provider

    """
    return providers['aws']


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
async def create_device_registration(request: DeviceRegistrationSingleRequest, fastapi_request: Request) -> DeviceRegistrationSingleResponse:
    """Creates a device registration, from a mobile app.

    Args:
    ----
        request (DeviceRegistrationSingleRequest): Data for the request

    Returns:
    -------
        Upon success, a DeviceRegistrationSingleResponse object is returned.

    """
    logger.info('Received device registration request: {}', request)

    response = DeviceRegistrationSingleResponse(
        endpoint_sid=str(uuid4()),
    )
    return response
