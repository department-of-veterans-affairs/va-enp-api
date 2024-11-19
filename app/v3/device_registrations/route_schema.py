"""Schema for device registration endpoints."""

from pydantic import AliasChoices, BaseModel, Field

from app.constants import MobileAppType, OSPlatformType


class DeviceRegistrationSingleRequest(BaseModel):
    """Request model for register endpoint."""

    device_name: str = Field(validation_alias=AliasChoices('device_name', 'deviceName'))
    device_token: str = Field(validation_alias=AliasChoices('device_token', 'deviceToken'))
    app_name: MobileAppType = Field(validation_alias=AliasChoices('app_name', 'appName'))
    os_name: OSPlatformType = Field(validation_alias=AliasChoices('os_name', 'osName'))


class DeviceRegistrationSingleResponse(BaseModel):
    """Response model for register endpoint."""

    endpoint_sid: str
