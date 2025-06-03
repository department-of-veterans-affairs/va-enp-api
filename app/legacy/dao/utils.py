"""Legacy dao utility helpers."""

import functools
from typing import Any

from cachetools import TTLCache
from pydantic import UUID4
from sqlalchemy import Row
from tenacity import retry, retry_if_exception_type, stop_after_attempt

from app.exceptions import RetryableError
from app.utils import log_last_attempt_on_failure, log_on_retry

_MAX_DB_RETRIES = 3  # Arbitrary


# Database retry parameters
db_retry = functools.partial(
    retry,
    before_sleep=log_on_retry,
    reraise=True,
    retry_error_callback=log_last_attempt_on_failure,
    retry=retry_if_exception_type(RetryableError),
    stop=stop_after_attempt(_MAX_DB_RETRIES),
)

_12_hours = float(12 * 60 * 60)
_5_minutes = float(5 * 60)

db_12h_cache: TTLCache[str, tuple[UUID4, str]] = TTLCache(maxsize=1024, ttl=_12_hours)
db_5m_cache: TTLCache[str, str | list[Row[Any]]] = TTLCache(maxsize=1024, ttl=_5_minutes)
