"""Base classes for exceptions."""

from typing import ANY


class RetryableError(Exception):
    """Indicative of a retryable exception."""

    def __init__(self, /, log_msg: str | None = None, *args: ANY, **kwargs: ANY) -> None:
        """Constructor."""
        self.log_msg = log_msg
        super().__init__(*args, **kwargs)


class NonRetryableError(Exception):
    """Indicative of a non-retryable exception."""

    def __init__(
        self,
        /,
        log_msg: str | None = None,
        status: str | None = None,
        status_reason: str | None = None,
        *args: ANY,
        **kwargs: ANY,
    ) -> None:
        """Constructor."""
        self.log_msg = log_msg
        self.status = status
        self.status_reason = status_reason
        super().__init__(*args, **kwargs)
