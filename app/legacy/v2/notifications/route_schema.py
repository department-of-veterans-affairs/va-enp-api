"""Request and Response bodies for /v2/notifications."""

import re
from typing import Annotated, Any, ClassVar, Collection, Literal

from phonenumbers import PhoneNumber
from pydantic import (
    UUID4,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    GetCoreSchemaHandler,
    HttpUrl,
    UrlConstraints,
    model_validator,
)
from pydantic_core import PydanticCustomError, core_schema
from pydantic_extra_types.phone_numbers import PhoneNumberValidator
from typing_extensions import Self

from app.constants import IdentifierType, MobileAppType, NotificationType
from app.legacy.v2.notifications.validators import is_valid_recipient_id_value


class StrictBaseModel(BaseModel):
    """Base model to enforce strict mode."""

    model_config = ConfigDict(strict=True)


class HttpsUrl(HttpUrl):
    """Enforced additional constraints on HttpUrl."""

    _constraints = UrlConstraints(max_length=255, allowed_schemes=['https'])


class V2Template(StrictBaseModel):
    """V2 templates have an associated version to conform to the notification-api database schema."""

    id: Annotated[UUID4, Field(strict=False)]
    uri: HttpUrl
    version: int


class RecipientIdentifierModel(StrictBaseModel):
    """Used to look up contact information from VA Profile or MPI."""

    id_type: Annotated[IdentifierType, Field(strict=False)]
    id_value: str

    @model_validator(mode='after')
    def validate_id(self) -> Self:
        """Validate recipient id_value based on id_type.

        Raises:
            ValueError: Bad input

        Returns:
            Self: this instance
        """
        if not is_valid_recipient_id_value(self.id_type, self.id_value):
            raise ValueError(f"Invalid id_value for id_type '{self.id_type}'")
        return self


class PhoneNumberValidator_RejectVanity(PhoneNumberValidator):
    """PhoneNumberValidator subclass that rejects vanity phone numbers when parsing from string."""

    def _vanity_check(self, phone_number: str | PhoneNumber) -> str | PhoneNumber:
        """Reject phone number strings with letters, after stripping known extension formats.

        Non-string argument passed through since they would have already been parsed or will be validated by base class.

        Args:
            phone_number (str | PhoneNumber): Input value.

        Raises:
            PydanticCustomError: Invalid phone number.

        Returns:
            str | PhoneNumber: Pass through value if valid or pre-processed PhoneNumber.
        """
        if isinstance(phone_number, str):
            # strip extensions
            cleaned_value = re.sub(r'\s*(x|ext|extension)\s*\d+$', '', phone_number, flags=re.IGNORECASE).strip()

            # do not allow letters in phone number (vanity)
            if re.search(r'[A-Za-z]', cleaned_value) is not None:
                raise PydanticCustomError('value_error', 'value is not a valid phone number')

        return phone_number

    def __get_pydantic_core_schema__(self, source: type[Any], handler: GetCoreSchemaHandler) -> core_schema.CoreSchema:
        """Construct Pydantic core validation schema to enforce proper validation order.

        Args:
            source (type[Any]): The source type of the field being validated.
            handler (GetCoreSchemaHandler): A handler that provides additional schema validation.

        Returns:
            core_schema.CoreSchema: A Pydantic validation schema.
        """
        return core_schema.chain_schema(
            [
                core_schema.no_info_before_validator_function(self._vanity_check, core_schema.str_schema()),
                super().__get_pydantic_core_schema__(source, handler),
            ]
        )


ValidatedPhoneNumber = Annotated[
    str,
    PhoneNumberValidator_RejectVanity(default_region='US', number_format='E164'),
]


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

    mobile_app: Annotated[MobileAppType, Field(strict=False)]
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

    id: Annotated[UUID4, Field(strict=False)]
    billing_code: str | None = Field(max_length=256, default=None)
    body: str
    callback_url: HttpsUrl | None = None
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
    type: Annotated[NotificationType, Field(strict=False)]


class V2GetEmailNotificationResponseModel(V2GetNotificationResponseModel):
    """Additional attributes when getting an e-mail notification."""

    email_address: EmailStr
    phone_number: None
    sms_sender_id: None
    subject: str


class V2GetSmsNotificationResponseModel(V2GetNotificationResponseModel):
    """Additional attributes when getting an SMS notification."""

    email_address: None
    phone_number: ValidatedPhoneNumber
    sms_sender_id: Annotated[UUID4, Field(strict=False)]
    subject: None


##################################################
# POST request for e-mail and SMS notifications
##################################################


class V2PostNotificationRequestModel(StrictBaseModel):
    """Common attributes for the POST /v2/notifications/<:notification_type> routes request."""

    billing_code: str | None = Field(max_length=256, default=None)
    callback_url: HttpsUrl | None = None
    personalisation: dict[str, str | int | float | list[str | int | float]] | None = None

    recipient_identifier: RecipientIdentifierModel | None = None
    reference: str | None = None
    template_id: Annotated[UUID4, Field(strict=False)]
    scheduled_for: Annotated[AwareDatetime, Field(strict=False)] | None = None


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

    phone_number: ValidatedPhoneNumber | None = None
    sms_sender_id: Annotated[UUID4, Field(strict=False)] | None = None

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
            raise ValueError('You must specify at least one of phone_number or recipient identifier.')
        return self


##################################################
# POST response for e-mail and SMS notifications
##################################################


class V2PostNotificationResponseModel(StrictBaseModel):
    """Common attributes for the POST /v2/notifications/<:notification_type> routes response."""

    id: Annotated[UUID4, Field(strict=False)]
    billing_code: str | None = Field(max_length=256, default=None)
    callback_url: HttpsUrl | None = None
    reference: str | None
    template: V2Template
    uri: HttpsUrl
    scheduled_for: Annotated[AwareDatetime, Field(strict=False)] | None = None


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
    from_number: ValidatedPhoneNumber


class V2PostSmsResponseModel(V2PostNotificationResponseModel):
    """Attributes specific to responses for sending SMS notifications."""

    content: V2SmsContentModel
