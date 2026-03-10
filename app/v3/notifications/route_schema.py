"""Request and Response bodies for v3/notifications."""

from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict


class RestrictiveBaseModel(BaseModel):
    """Base model to prevent additional properties without strict type checking."""

    model_config = ConfigDict(strict=False, extra='forbid')


class NotificationSingleRequest(RestrictiveBaseModel):
    """Request model for notification endpoint."""

    to: str
    personalization: dict[str, str] | None = None
    template: UUID

    def serialize(self) -> dict[str, str | dict[str, str] | None]:
        """Serialize the pydantic model.

        Returns:
            dict[str, None | str | dict[str, str]]: Serialized version of the model

        """
        serialized = self.model_dump()
        serialized['template'] = str(serialized['template'])
        return serialized


class NotificationSingleResponse(BaseModel):
    """Response for notification endpoint."""

    id: UUID
    created_at: AwareDatetime
    updated_at: AwareDatetime
    sent_at: AwareDatetime | None = None
    to: str
