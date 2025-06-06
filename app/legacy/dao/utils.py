"""Legacy dao utility helpers."""

import os

from itsdangerous import URLSafeSerializer
from tenacity import retry, retry_if_exception_type, stop_after_attempt

from app.exceptions import RetryableError
from app.utils import log_last_attempt_on_failure, log_on_retry

_MAX_DB_RETRIES = 3  # Arbitrary


# Database retry parameters
db_retry = retry(
    before_sleep=log_on_retry,
    reraise=True,
    retry_error_callback=log_last_attempt_on_failure,
    retry=retry_if_exception_type(RetryableError),
    stop=stop_after_attempt(_MAX_DB_RETRIES),
)


class Serializer:
    """A class to handle serialization and deserialization of objects using URL-safe serialization."""

    def __init__(self) -> None:
        """Initialize the Serializer class with a URLSafeSerializer."""
        self.serializer = URLSafeSerializer(os.environ.get('SECRET_KEY', 'local_secret'))
        self.salt = os.environ.get('DANGEROUS_SALT', 'local_salt')

    def serialize(
        self,
        thing_to_encrypt: object | str | bytes | dict | list | tuple | int | float | bool | None,
    ) -> str:
        """Serialize an object into a URL-safe string.

        Args:
            thing_to_encrypt (object | str | bytes | dict | list | tuple | int | float | bool | None): The object to serialize.

        Returns:
            str: The serialized object as a URL-safe string.
        """
        return self.serializer.dumps(thing_to_encrypt, salt=self.salt)

    def deserialize(
        self,
        thing_to_decrypt: str,
    ) -> object | str | bytes | dict | list | tuple | int | float | bool | None:
        """Deserialize a URL-safe string back into an object.

        Args:
            thing_to_decrypt (str): The URL-safe string to deserialize.

        Returns:
            object | str | bytes | dict | list | tuple | int | float | bool | None: The deserialized object.
        """
        return self.serializer.loads(thing_to_decrypt, salt=self.salt)
