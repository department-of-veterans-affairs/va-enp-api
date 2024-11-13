from time import monotonic
from typing import Any, Callable, Coroutine
from uuid import uuid4

from fastapi.routing import APIRoute

from fastapi import Request, HTTPException, Response


class RegisterDeviceRoute(APIRoute):
    """Exception and logging handling."""

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        """Override default handler.

        Returns
        -------
            Callable: the route handler

        """
        async def custom_route_handler(request: Request) -> Response:
            raise HTTPException(501, 'Not implemented')

        return custom_route_handler