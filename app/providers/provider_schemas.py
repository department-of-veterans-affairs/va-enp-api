"""Define schemas for sending various types of notificaitons."""

from pydantic import BaseModel, model_validator
from typing_extensions import Self


class PushModel(BaseModel):
    """Define the input to send a push notification.

    As currently implemented, it is idiosyncratic to sending push notifications to the VA Mobile App using AWS SNS.
    """

    Message: str
    TargetArn: str | None = None
    TopicArn: str | None = None

    @model_validator(mode='after')
    def check_arn(self) -> Self:
        """One, and only one, of TopicArn or TargetArn must not be None.

        Raises
        ------
            ValueError: Bad input

        Returns
        -------
            Self: this instance

        """
        if (self.TargetArn is None and self.TopicArn is None) or (
            self.TargetArn is not None and self.TopicArn is not None
        ):
            raise ValueError('One, and only one, of TopicArn or TargetArn must not be None.')
        return self
