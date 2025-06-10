"""Legacy client utility helpers."""

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_full_jitter, wait_none

from app.constants import DEPLOYMENT_ENVS, ENV
from app.exceptions import RetryableError
from app.utils import log_last_attempt_on_failure, log_on_retry

_MAX_CLIENT_RETRIES = 5  # Arbitrary


# Client retry parameters
client_retry = retry(
    before_sleep=log_on_retry,
    reraise=True,
    retry_error_callback=log_last_attempt_on_failure,
    retry=retry_if_exception_type(RetryableError),
    stop=stop_after_attempt(_MAX_CLIENT_RETRIES),
    wait=wait_full_jitter(multiplier=1, max=60) if ENV in DEPLOYMENT_ENVS else wait_none(),
)
