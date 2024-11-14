"""Request and Response bodies for v2/notifications."""

from pydantic import BaseModel

from app.constants import IdentifierTypeICN, MobileAppType


class V2NotificationPushRequest(BaseModel):
    """Request model for the v2 push notification endpoint."""

    class ICNRecipientIdentifier(BaseModel):
        """Model for ICN recipient identifier."""

        # created a specific enum for ICN so api spec is clear, and only "ICN" is allowed
        id_type: IdentifierTypeICN
        id_value: str

    mobile_app: MobileAppType
    # This is a string in the Flask API. It will be a UUID4 in v3.
    template_id: str
    recipient_identifier: ICNRecipientIdentifier
    personalisation: dict[str, str | int | float] | None = None


class V2NotificationPushResponse(BaseModel):
    """Response model for v2 push notification endpoint."""

    result: str = 'success'
