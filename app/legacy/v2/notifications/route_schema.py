"""Request and Response bodies for /v2/notifications."""

import datetime
from typing import Annotated, ClassVar, Collection, Literal
from uuid import UUID

from pydantic import (
    UUID4,
    AfterValidator,
    AwareDatetime,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    EmailStr,
    Field,
    HttpUrl,
    model_validator,
)
from typing_extensions import Self

from app.constants import AttachmentSendingMethodType, IdentifierType, MobileAppType, NotificationType, PhoneNumberE164


def uuid4_before_validator(value: str | UUID | None) -> UUID | None:
    """Validates and converts input to a UUID v4 object allowing None for defaults.

    Args:
        value (Any): The input value to validate. It can be:
            - A UUID v4 object.
            - A string representation of a UUID v4.
            - None

    Returns:
        UUID | None: A validated UUID v4 object or None as a dafault.

    Raises:
        ValueError: If the input is not a valid UUID v4 or cannot be converted into one.
    """
    if value is None:
        return None

    if isinstance(value, UUID):
        if value.version != 4:
            raise ValueError('UUID must be version 4')
        return value

    if isinstance(value, str):
        return parse_uuid4(value)

    raise ValueError('Expected a valid UUID4 (string or UUID object)')


def parse_uuid4(value: str) -> UUID:
    """Parses and validates a UUID v4 from a string.

    Args:
        value (str): A string representation of a UUID v4.

    Returns:
        UUID: A validated UUID v4 object or None as a dafault.

    Raises:
        ValueError: If the input cannot be converted to a UUID v4.
    """
    try:
        uuid_obj = UUID(value)
        if uuid_obj.version != 4:
            raise ValueError('UUID must be version 4')
        return uuid_obj
    except ValueError:
        raise ValueError('Expected a valid UUID4 (string or UUID object)')


def validate_url_scheme(url: HttpUrl | None) -> HttpUrl | None:
    """Validator to enforce HTTPS scheme for callback URLs.

    This method ensures that the `callback_url` is either:
    - `None` (if not provided)
    - A valid HTTPS URL (URLs with `http://` are rejected)

    Args:
        url (HttpUrl | None): The callback URL to validate.

    Returns:
        HttpUrl | None: The validated URL if it's HTTPS, or `None` if not provided.

    Raises:
        ValueError: If the provided URL is not using HTTPS.
    """
    if url and url.scheme != 'https':
        raise ValueError('Only HTTPS URLs are allowed')
    return url


class StrictBaseModel(BaseModel):
    """Base model to enforce strict mode."""

    model_config = ConfigDict(strict=True)


class V2Template(StrictBaseModel):
    """V2 templates have an associated version to conform to the notification-api database schema."""

    id: Annotated[UUID4, BeforeValidator(uuid4_before_validator)]
    uri: HttpUrl
    version: int


class RecipientIdentifierModel(StrictBaseModel):
    """Used to look up contact information from VA Profile or MPI."""

    id_type: IdentifierType
    id_value: str


##################################################
# POST request and response for push notifications
##################################################


class V2PostPushRequestModel(StrictBaseModel):
    """Request model for the v2 push notification endpoint."""

    class ICNRecipientIdentifierModel(StrictBaseModel):
        """Model for ICN recipient identifier."""

        # Created a specific enum for ICN so api spec is clear, and only "ICN" is allowed.
        id_type: Literal[IdentifierType.ICN]
        id_value: str

    mobile_app: MobileAppType
    # This is a string in the Flask API. It will be a UUID4 in v3.
    template_id: str
    recipient_identifier: ICNRecipientIdentifierModel
    personalisation: dict[str, str | int | float] | None = None


class V2PostPushResponseModel(StrictBaseModel):
    """Response model for v2 push notification endpoint."""

    result: str = 'success'


##################################################
# GET response for /v2/notifications/<:id>
##################################################


class V2GetNotificationResponseModel(StrictBaseModel):
    """Common attributes for the GET /v2/notifications/<:id> route response."""

    id: UUID4
    billing_code: str | None = Field(max_length=256, default=None)
    body: str
    callback_url: HttpUrl | None = Field(max_length=255, default=None)
    completed_at: AwareDatetime | None
    cost_in_millicents: float
    created_at: AwareDatetime
    created_by_name: str | None
    provider_reference: str | None
    recipient_identifiers: list[RecipientIdentifierModel] | None
    reference: str | None
    segments_count: int
    sent_at: AwareDatetime | None
    sent_by: str | None
    status: str
    status_reason: str | None
    template: V2Template
    type: NotificationType


class V2GetEmailNotificationResponseModel(V2GetNotificationResponseModel):
    """Additional attributes when getting an e-mail notification."""

    email_address: EmailStr
    phone_number: None
    sms_sender_id: None
    subject: str


class V2GetSmsNotificationResponseModel(V2GetNotificationResponseModel):
    """Additional attributes when getting an SMS notification."""

    email_address: None
    phone_number: PhoneNumberE164
    sms_sender_id: Annotated[UUID4, BeforeValidator(uuid4_before_validator)]
    subject: None


##################################################
# POST request for e-mail and SMS notifications
##################################################


class PersonalisationFileObject(StrictBaseModel):
    """Personalisation file attachment object."""

    file: str
    filename: str = Field(..., min_length=3, max_length=255)
    sending_method: AttachmentSendingMethodType | None = None


class V2PostNotificationRequestModel(StrictBaseModel):
    """Common attributes for the POST /v2/notifications/<:notification_type> routes request."""

    billing_code: str | None = Field(max_length=256, default=None)
    callback_url: Annotated[
        HttpUrl | None,
        Field(max_length=255, default=None),
        AfterValidator(validate_url_scheme),
    ] = None
    personalisation: dict[str, str | int | float | list[str | int | float] | PersonalisationFileObject] | None = None

    recipient_identifier: RecipientIdentifierModel | None = None
    reference: str | None = None
    template_id: Annotated[UUID4, BeforeValidator(uuid4_before_validator)]
    scheduled_for: datetime.datetime | None = None
    email_reply_to_id: Annotated[UUID | None, BeforeValidator(uuid4_before_validator)] = None


class V2PostEmailRequestModel(V2PostNotificationRequestModel):
    """Attributes specific to requests to send e-mail notifications."""

    email_address: EmailStr | None = None

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
            raise ValueError('You must specify one of "email_address" or "recipient identifier".')
        return self


class V2PostSmsRequestModel(V2PostNotificationRequestModel):
    """Attributes specific to requests to send SMS notifications."""

    phone_number: PhoneNumberE164 | None = None
    sms_sender_id: Annotated[UUID | None, BeforeValidator(uuid4_before_validator)] = None

    json_schema_extra: ClassVar[dict[str, dict[str, Collection[str]]]] = {
        'examples': {
            'phone number': {
                'summary': 'phone number',
                'description': 'Send an SMS notification to a phone number.',
                'value': {
                    'billing_code': '12345',
                    'callback_url': 'https://example.com/',
                    'personalisation': {
                        'additionalProp1': 'string',
                        'additionalProp2': 'string',
                        'additionalProp3': 'string',
                    },
                    'reference': 'an-external-id',
                    'template_id': 'a71400e3-b2f8-4bd1-91c0-27f9ca7106a1',
                    'phone_number': '+18005550101',
                    'sms_sender_id': '4f44ffc8-1ff8-4832-b1af-0b615691b6ea',
                },
            },
            'recipient identifier': {
                'summary': 'recipient identifier',
                'description': 'Send an SMS notification to a recipient identifier.',
                'value': {
                    'billing_code': 'string',
                    'callback_url': 'https://example.com/',
                    'personalisation': {
                        'additionalProp1': 'string',
                        'additionalProp2': 'string',
                        'additionalProp3': 'string',
                    },
                    'reference': 'string',
                    'template_id': 'a71400e3-b2f8-4bd1-91c0-27f9ca7106a1',
                    'sms_sender_id': '4f44ffc8-1ff8-4832-b1af-0b615691b6ea',
                    'recipient_identifier': {'id_type': 'ICN', 'id_value': 'not-a-valid-icn'},
                },
            },
        },
    }

    @model_validator(mode='after')
    def phone_number_or_recipient_id(self) -> Self:
        """At least one, of 'phone_number' or 'recipient_identifier' must not be None.

        Raises:
            ValueError: Bad input

        Returns:
            Self: this instance

        """
        if self.phone_number is None and self.recipient_identifier is None:
            raise ValueError('You must specify at least one of "phone_number" or "recipient identifier".')
        return self


##################################################
# POST response for e-mail and SMS notifications
##################################################


class V2PostNotificationResponseModel(StrictBaseModel):
    """Common attributes for the POST /v2/notifications/<:notification_type> routes response."""

    id: Annotated[UUID4, BeforeValidator(uuid4_before_validator)]
    billing_code: str | None = Field(max_length=256, default=None)
    callback_url: HttpUrl | None = Field(max_length=255, default=None)
    reference: str | None
    template: V2Template
    uri: HttpUrl
    scheduled_for: datetime.datetime | None = None


class V2EmailContentModel(StrictBaseModel):
    """The content body of a response for sending an e-mail notification."""

    body: str
    subject: str


class V2PostEmailResponseModel(V2PostNotificationResponseModel):
    """Attributes specific to responses for sending e-mail notifications."""

    content: V2EmailContentModel


class V2SmsContentModel(StrictBaseModel):
    """The content body of a response for sending an SMS notification."""

    body: str
    from_number: PhoneNumberE164


class V2PostSmsResponseModel(V2PostNotificationResponseModel):
    """Attributes specific to responses for sending SMS notifications."""

    content: V2SmsContentModel
