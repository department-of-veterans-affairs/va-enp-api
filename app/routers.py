"""FastAPI routers."""

from time import monotonic
from typing import Any, Callable, Coroutine

from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.routing import APIRoute
from loguru import logger

from app.constants import RESPONSE_400, RESPONSE_500


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
            except Exception as e:
                status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
                logger.exception('{}: {}', RESPONSE_500, type(e).__name__)
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=RESPONSE_500)
            finally:
                logger.info(
                    '{} {} {} {}s',
                    request.method,
                    request.url,
                    status_code,
                    f'{(monotonic() - start):6f}',
                )

        return custom_route_handler
