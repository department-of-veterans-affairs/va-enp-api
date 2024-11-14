"""Request and Response bodies for v3/notifications."""

from pydantic import UUID4, AwareDatetime, BaseModel


class NotificationSingleRequest(BaseModel):
    """Request model for notification endpoint."""

    to: str
    personalization: None | dict[str, str] = None
    template: UUID4

    def serialize(self) -> dict[str, None | str | dict[str, str]]:
        """Serialize the pydantic model.

        Returns:
        -------
            dict[str, None | str | dict[str, str]]: Serialized version of the model

        """
        serialized = self.model_dump()
        serialized['template'] = str(serialized['template'])
        return serialized


class NotificationSingleResponse(BaseModel):
    """Response for notification endpoint."""

    id: UUID4
    created_at: AwareDatetime
    updated_at: AwareDatetime
    sent_at: None | AwareDatetime = None
    to: str
