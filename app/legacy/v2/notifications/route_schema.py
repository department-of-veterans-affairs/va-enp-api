"""Request and Response bodies for v2/notifications."""

from pydantic import UUID4, AwareDatetime, BaseModel

from app.constants import IdentifierTypeICN, MobileAppType


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


class V2NotificationPushRequest(BaseModel):
    """Request model for the v2 push notification endpoint."""

    class ICNRecipientIdentifier(BaseModel):  # are we using pydantic models or dataclasses for stuff like this?
        """Model for ICN recipient identifier."""

        id_type: IdentifierTypeICN  # made specific enum for ICN so api spec is clear
        id_value: str

    mobile_app: MobileAppType
    template_id: str  # this is a string in the API
    recipient_identifier: ICNRecipientIdentifier
    personalization: dict[str, str] | None = None


class V2NotificationPushResponse(BaseModel):
    """Response model for v2 push notification endpoint."""

    result: str = 'success'
