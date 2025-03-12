"""Base classes for exceptions."""


class RetryableError(Exception):
    """Indicative of a retryable exception."""

    def __init__(self, /, log_msg: str | None = None, *args: str, **kwargs: str) -> None:
        """Constructor.

        Arguments:
            log_msg: Additional information for the logs
            *args: Self-explanatory
            **kwargs: Self-explanatory
        """
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
        *args: str,
        **kwargs: str,
    ) -> None:
        """Constructor.

        Arguments:
            log_msg: Additional information for the logs
            status: The notification status
            status_reason: The reason for the notification status
            *args: Self-explanatory
            **kwargs: Self-explanatory
        """
        self.log_msg = log_msg
        self.status = status
        self.status_reason = status_reason
        super().__init__(*args, **kwargs)
