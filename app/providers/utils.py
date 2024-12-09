"""Utils for logging retry information."""

from loguru import logger
from tenacity import RetryCallState


def log_on_retry(retry_state: RetryCallState) -> None:
    """Log the result of the last call attempt if it failed.

    Args:
        retry_state (RetryCallState): The state of the last call attempt.

    """
    fn_name = f'{retry_state.fn.__module__}.{retry_state.fn.__name__}'

    logger.info(
        'Retrying {}: attempt {} raised {}: "{}" retrying in {:.3f} seconds.',
        fn_name,
        retry_state.attempt_number,
        retry_state.outcome.exception().__class__.__name__,
        retry_state.outcome.exception(),
        retry_state.next_action.sleep,
    )


def log_last_attempt_on_failure(retry_state: RetryCallState) -> None:
    """Log the last retry attempt because it failed. Raise the exception.

    Args:
        retry_state (RetryCallState): The state of the last call attempt.

    Raises:
        The exception raised by the last retry attempt.

    """
    fn_name = f'{retry_state.fn.__module__}.{retry_state.fn.__name__}'

    logger.warning(
        'Task failure {}: attempted {} times, raised {}: "{}" after {:.3f} seconds.',
        fn_name,
        retry_state.attempt_number,
        retry_state.outcome.exception().__class__.__name__,
        retry_state.outcome.exception(),
        retry_state.idle_for,
    )

    raise retry_state.outcome.exception()
