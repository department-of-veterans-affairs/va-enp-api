"""Legacy dao utility helpers."""

import functools

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
