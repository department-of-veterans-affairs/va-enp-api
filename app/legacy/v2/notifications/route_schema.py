"""Request and Response bodies for /v2/notifications."""

from datetime import datetime
from typing import Literal

from pydantic import UUID4, BaseModel, EmailStr, Field, HttpUrl, model_validator
from typing_extensions import Self

from app.constants import EMAIL_TYPE, IdentifierTypeICN, MobileAppType, PUSH_TYPE, SMS_TYPE


class V2Template(BaseModel):
    """V2 templates have an associated version to conform to the notification-api database schema."""

    id: UUID4
    uri: HttpUrl
    version: int


class RecipientIdentifierModel(BaseModel):
    """Used to look up contact information from VA Profile or MPI."""
    id_type: str
    id_value: str


##################################################
# POST request and response for push notifications
##################################################


class V2PostPushRequestModel(BaseModel):
    """Request model for the v2 push notification endpoint."""

    class ICNRecipientIdentifierModel(BaseModel):
        """Model for ICN recipient identifier."""

        # Created a specific enum for ICN so api spec is clear, and only "ICN" is allowed.
        id_type: IdentifierTypeICN
        id_value: str

    mobile_app: MobileAppType
    # This is a string in the Flask API. It will be a UUID4 in v3.
    template_id: str
    recipient_identifier: ICNRecipientIdentifierModel
    personalisation: dict[str, str | int | float] | None = None


class V2PostPushResponseModel(BaseModel):
    """Response model for v2 push notification endpoint."""

    result: str = 'success'


##################################################
# GET response for /v2/notifications/<:id>
##################################################


class V2GetNotificationResponseModel(BaseModel):
    """Common attributes for the GET /v2/notifications/<:id> route response."""

    id: UUID4
    billing_code: str | None
    body: str
    callback_url: HttpUrl | None
    completed_at: datetime | None
    cost_in_millicents: float
    created_at: datetime
    created_by_name: str | None
    provider_reference: str | None
    recipient_identifiers: list[RecipientIdentifierModel] | None
    reference: str | None
    segments_count: int
    sent_at: datetime | None
    sent_by: str | None
    status: str
    status_reason: str | None
    template: V2Template
    # This line fails mypy because "type" is a Python built-in function.
    type: Literal[EMAIL_TYPE, PUSH_TYPE, SMS_TYPE]  # type: ignore


class V2GetEmailNotificationModel(V2GetNotificationResponseModel):
    """Additional attributes when getting an e-mail notification."""

    email_address: EmailStr
    phone_number: None
    sms_sender_id: None
    subject: str


class V2GetSmsNotificationModel(V2GetNotificationResponseModel):
    """Additional attributes when getting an SMS notification."""

    email_address: None
    phone_number: str
    sms_sender_id: UUID4
    subject: None


##################################################
# POST request for e-mail and SMS notifications
##################################################


class V2PostNotificationRequestModel(BaseModel):
    """Common attributes for the POST /v2/notifications/<:notification_type> routes request."""
    billing_code: str | None = Field(max_length=256, default=None)
    callback_url: HttpUrl | None = None
    personalisation: dict[str, str | int | float] | None = None
    recipient_identifier: RecipientIdentifierModel | None = None
    reference: str | None = None
    template_id: UUID4


class V2PostEmailRequestModel(V2PostNotificationRequestModel):
    """Attributes specific to requests to send e-mail notifications."""
    email_address: EmailStr
    email_reply_to_id: UUID4

    @model_validator(mode='after')
    def email_or_recipient_id(self) -> Self:
        """One, and only one, of "email_address" or "recipient_identifier" must not be None.

        Raises:
            ValueError: Bad input

        Returns:
            Self: this instance

        """
        if (self.email_address is None and self.recipient_identifier is None) or (
            self.email_address is not None and self.recipient_identifier is not None
        ):
            raise ValueError(
                'You must specify an e-mail address or recipient identifier; not both.'
            )
        return self


class V2PostSmsRequestModel(V2PostNotificationRequestModel):
    """Attributes specific to requests to send SMS notifications."""
    phone_number: str
    sms_sender_id: UUID4

    @model_validator(mode='after')
    def phone_number_or_recipient_id(self) -> Self:
        """One, and only one, of "phone_number" or "recipient_identifier" must not be None.

        Raises:
            ValueError: Bad input

        Returns:
            Self: this instance

        """
        if (self.phone_number is None and self.recipient_identifier is None) or (
            self.phone_number is not None and self.recipient_identifier is not None
        ):
            raise ValueError(
                'You must specify a phone number or recipient identifier; not both.'
            )
        return self


##################################################
# POST response for e-mail and SMS notifications
##################################################


class V2PostNotificationResponseModel(BaseModel):
    """Common attributes for the POST /v2/notifications/<:notification_type> routes response."""

    id: UUID4
    billing_code: str | None
    callback_url: HttpUrl | None
    reference: str | None
    template: V2Template
    uri: HttpUrl


class V2EmailContentModel(BaseModel):
    """The content body of a response for sending an e-mail notification."""
    body: str
    subject: str


class V2PostEmailResponseModel(V2PostNotificationResponseModel):
    """Attributes specific to responses for sending e-mail notifications."""
    content: V2EmailContentModel


class V2SmsContentModel(BaseModel):
    """The content body of a response for sending an SMS notification."""
    body: str
    from_number: str


class V2PostSmsResponseModel(V2PostNotificationResponseModel):
    """Attributes specific to responses for sending SMS notifications."""
    content: V2SmsContentModel
