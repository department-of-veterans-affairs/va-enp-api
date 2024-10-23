"""Request and Response bodies for v2/notifications."""

from pydantic import UUID4, AwareDatetime, BaseModel


class V2NotificationSingleRequest(BaseModel):
    """Request model for v2 notification endpoint.

    Note: This is just a placeholder model for now. Please replace or update when working enp-45
    """

    personalisation: dict[str, str] | None = None
    reference: str | None = None
    template_id: UUID4
    to: str

    def serialize(self) -> dict[str, None | str | dict[str, str]]:
        """Serialize the pydantic model.

        Returns
        -------
            dict[str, None | str | dict[str, str]]: Serialized version of the model

        """
        serialized = self.model_dump()
        serialized['template_id'] = str(serialized['template_id'])
        return serialized


class V2NotificationSingleResponse(BaseModel):
    """Response for v2 notification endpoint.

    Note: This is just a placeholder model for now. Please replace or update when working enp-45
    """

    id: UUID4
    created_at: AwareDatetime
    updated_at: AwareDatetime
    sent_at: None | AwareDatetime = None
    to: str
