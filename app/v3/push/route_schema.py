from pydantic import AliasChoices, BaseModel, Field


class RegisterSingleRequest(BaseModel):
    """Request model for register endpoint."""

    device_name: str = Field(validation_alias=AliasChoices('device_name', 'deviceName')) 
    device_token: str = Field(validation_alias=AliasChoices('device_token', 'deviceToken'))
    app_name: str = Field(validation_alias=AliasChoices('app_name', 'appName'))
    os_name: str = Field(validation_alias=AliasChoices('os_name', 'osName'))
    debug: bool = False