"""FastAPI routers."""

from time import monotonic
from typing import Any, Callable, Coroutine

from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.routing import APIRoute
from loguru import logger

from app.constants import RESPONSE_400


class LegacyTimedAPIRoute(APIRoute):
    """Exception and logging handling for v2/legacy."""

    @staticmethod
    def http_exception_handler(request: Request, e: HTTPException) -> JSONResponse:
        """Log and handle HTTPException errors.

        Args:
            request (Request): The original request data.
            e (HTTPException): The exception data.

        Returns:
            JSONResponse: The JSON response when v2 validation errors are present.
        """
        logger.warning(
            'Request: {} {} Failed with HTTPException: {}',
            request.method,
            request.url,
            e,
        )

        # Return the JSON response for v2 compatibility
        if isinstance(e.detail, dict) and e.detail.get('errors'):
            return JSONResponse(status_code=e.status_code, content=e.detail)
        elif e.status_code in (401, 403):
            errors = {'errors': [{'error': 'AuthError', 'msg': e.detail}], 'status_code': e.status_code}
            return JSONResponse(status_code=e.status_code, content=errors)
        else:
            raise e

    @staticmethod
    def request_validation_error_handler(request: Request, e: RequestValidationError) -> JSONResponse:
        """Log and handle RequestValidationError errors.

        Convert Pydantic/FastAPI errors structure to a v2 json response.

        Args:
            request (Request): The original request data.
            e (RequestValidationError): The exception data.

        Returns:
            JSONResponse: The JSON response when validation errors are present.
        """
        status_code = status.HTTP_400_BAD_REQUEST

        logger.warning(
            'Request: {} {} Failed validation: {}',
            request.method,
            request.url,
            e,
        )

        errors = []

        for error in e.errors():
            error_location = error.get('loc')
            error_message = error.get('msg')

            if error.get('type') == 'uuid_parsing':
                # special case to override verbose Pydantic UUID format message
                error_message = 'Input should be a valid UUID'

            if len(error_location) > 1:
                # prepend last entry in error location if available, skip global and leading context
                error_message = f'{error_location[-1]}: {error_message}'

            errors.append({'error': 'ValidationError', 'message': error_message})

        return JSONResponse(status_code=status_code, content={'errors': errors, 'status_code': status_code})

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        """Override default handler.

        Returns:
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
            except RequestValidationError as e:
                status_code = status.HTTP_400_BAD_REQUEST
                return self.request_validation_error_handler(request, e)
            except HTTPException as e:
                status_code = e.status_code
                return self.http_exception_handler(request, e)
            finally:
                logger.info(
                    '{} {} {} {}s',
                    request.method,
                    request.url,
                    status_code,
                    f'{(monotonic() - start):6f}',
                )

        return custom_route_handler


class TimedAPIRoute(APIRoute):
    """Exception and logging handling."""

    @staticmethod
    def http_exception_handler(request: Request, e: HTTPException) -> JSONResponse:
        """Log and handle HTTPException errors.

        Args:
            request (Request): The original request data.
            e (HTTPException): The exception data.

        Returns:
            JSONResponse: The JSON response when v2 validation errors are present.
        """
        logger.warning(
            'Request: {} {} Failed with HTTPException: {}',
            request.method,
            request.url,
            e,
        )

        # Return the JSON response for v2 compatibility
        if isinstance(e.detail, dict) and e.detail.get('errors'):
            return JSONResponse(status_code=e.status_code, content=e.detail)
        else:
            raise e

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        """Override default handler.

        Returns:
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
            except RequestValidationError as e:
                status_code = status.HTTP_400_BAD_REQUEST
                logger.warning(
                    'Request: {} {} Failed validation: {}',
                    request.method,
                    request.url,
                    e,
                )
                raise HTTPException(400, f'{RESPONSE_400} - {e}')
            except HTTPException as e:
                status_code = e.status_code
                return self.http_exception_handler(request, e)
            finally:
                logger.info(
                    '{} {} {} {}s',
                    request.method,
                    request.url,
                    status_code,
                    f'{(monotonic() - start):6f}',
                )

        return custom_route_handler
