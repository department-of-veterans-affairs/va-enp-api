"""Worker ID plugin for starlette-context."""

import os
from typing import Optional

from starlette.requests import HTTPConnection
from starlette_context.plugins.base import Plugin


class WorkerIdPlugin(Plugin):
    """Plugin to add Gunicorn/Uvicorn worker ID to request context."""

    key = 'worker_id'

    async def process_request(self, request: HTTPConnection) -> Optional[int]:
        """Add worker ID to request context.

        Args:
            request: The incoming HTTP connection

        Returns:
            The worker process ID
        """
        # Get the current process ID which represents the worker ID
        return os.getpid()
