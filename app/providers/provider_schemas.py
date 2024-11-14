"""Define schemas for sending various types of notificaitons."""

from pydantic import BaseModel, model_validator
from typing_extensions import Self


class PushModel(BaseModel):
    """Define the input to send a push notification.

    As currently implemented, it is idiosyncratic to sending push notifications to the VA Mobile App using AWS SNS.
    """

    message: str
    target_arn: str | None = None
    topic_arn: str | None = None

    @model_validator(mode='after')
    def check_arn(self) -> Self:
        """One, and only one, of topic_arn or target_arn must not be None.

        Raises:
        ------
            ValueError: Bad input

        Returns:
        -------
            Self: this instance

        """
        if (self.target_arn is None and self.topic_arn is None) or (
            self.target_arn is not None and self.topic_arn is not None
        ):
            raise ValueError('One, and only one, of topic_arn or target_arn must not be None.')
        return self


class PushRegistrationModel(BaseModel):
    """Define the input to register a device that will receive push notifications.

    As currently implemented, this class is idiosyncratic to AWS SNS and includes only required parameters.
    """

    platform_application_arn: str
    token: str
