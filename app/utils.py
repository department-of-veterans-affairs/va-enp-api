"""Utils for logging retry information."""

from tenacity import RetryCallState

from app.logging.logging_config import logger


def log_on_retry(retry_state: RetryCallState) -> None:
    """Log the result of the last call attempt if it failed.

    Args:
        retry_state (RetryCallState): The state of the last call attempt.

    """
    fn_name = f'{retry_state.fn.__module__}.{retry_state.fn.__name__}'  # type: ignore

    logger.warning(
        'Retrying {}: attempt {} raised {}: retrying in {:.3f} seconds.',
        fn_name,
        retry_state.attempt_number,
        retry_state.outcome.exception().__class__.__name__,  # type: ignore
        retry_state.next_action.sleep,  # type: ignore
    )


def log_last_attempt_on_failure(retry_state: RetryCallState) -> None:
    """Log the last retry attempt because it failed. Raise the exception.

    Args:
        retry_state (RetryCallState): The state of the last call attempt.

    Raises:
        The exception raised by the last retry attempt.

    """
    fn_name = f'{retry_state.fn.__module__}.{retry_state.fn.__name__}'  # type: ignore

    logger.exception(
        'Task failure {}: attempted {} times, raised {} after {:.3f} seconds.',
        fn_name,
        retry_state.attempt_number,
        retry_state.outcome.exception().__class__.__name__,  # type: ignore
        retry_state.idle_for,
    )

    # TODO: Update notification to failure here. Max retries exceeded.
