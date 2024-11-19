"""FastAPI routers."""

from time import monotonic
from typing import Any, Callable, Coroutine

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import Response
from fastapi.routing import APIRoute
from loguru import logger

from app.constants import RESPONSE_400, RESPONSE_500


class TimedAPIRoute(APIRoute):
    """Exception and logging handling."""

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
                status_code = 400
                logger.warning(
                    'Request: {} Failed validation: {}',
                    request,
                    e,
                )
                raise HTTPException(400, f'{RESPONSE_400} - {e}')
            except HTTPException as e:
                status_code = e.status_code
                logger.warning(
                    'Request: {} Failed with HTTPException: {}',
                    request,
                    e,
                )
                raise e
            except Exception as e:
                status_code = 500
                logger.exception('{}: {}', RESPONSE_500, type(e).__name__)
                raise HTTPException(status_code, RESPONSE_500)
            finally:
                logger.info(
                    '{} {} {} {}s',
                    request.method,
                    request.url,
                    status_code,
                    f'{(monotonic() - start):6f}',
                )

        return custom_route_handler
