"""Base classes for exceptions."""


class RetryableError(Exception):
    """Indicative of a retryable exception."""

    ...


class NonRetryableError(Exception):
    """Indicative of a non-retryable exception."""

    ...
