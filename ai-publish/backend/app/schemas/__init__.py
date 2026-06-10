from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_serializer


def format_utc_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    username: str
    password: str


class PlatformAccountCreate(BaseModel):
    platform: str = "xhs"
    account_name: str


class PlatformAccountResponse(BaseModel):
    id: int
    platform: str
    account_name: str
    status: str
    created_at: datetime

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime) -> str:
        return format_utc_datetime(value) or ""

    class Config:
        from_attributes = True


class LoginAccountResponse(BaseModel):
    success: bool
    status: str
    message: str
    qrcode_path: str | None = None
    qrcode_data_url: str | None = None
    session_id: str | None = None


class LoginSessionResponse(BaseModel):
    session_id: str
    account_id: int
    status: str
    success: bool = False
    message: str = ""
    qrcode_data_url: str | None = None
    login_status: str | None = None


class CookieCheckResponse(BaseModel):
    valid: bool
    status: str


class TextGenerateRequest(BaseModel):
    topic: str
    platform: str = "xhs"
    style: str = "default"


class ImageGenerateRequest(BaseModel):
    topic: str
    platform: str = "xhs"
    ratio: str = "3:4"
    style: str = "default"
    count: int = Field(default=1, ge=1, le=4)
    cover_text: str | None = None


class MaterialResponse(BaseModel):
    id: int
    type: str
    source: str
    name: str | None = None
    category: str | None = None
    file_path: str
    url: str | None
    created_at: datetime

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime) -> str:
        return format_utc_datetime(value) or ""

    class Config:
        from_attributes = True


class PublishTaskCreate(BaseModel):
    title: str
    content: str | None = None
    comment_guide: str | None = None
    topic: str | None = None
    cover_text: str | None = None
    wizard_step: int | None = Field(default=None, ge=0, le=4)
    tags: list[str] = Field(default_factory=list)
    platform: str = "xhs"
    account_id: int
    content_type: str = "note"
    material_ids: list[int] = Field(default_factory=list)
    publish_time: datetime | None = None
    submit: bool = False


class PublishTaskUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    comment_guide: str | None = None
    topic: str | None = None
    cover_text: str | None = None
    wizard_step: int | None = Field(default=None, ge=0, le=4)
    tags: list[str] | None = None
    account_id: int | None = None
    material_ids: list[int] | None = None
    publish_time: datetime | None = None


class MaterialSummary(BaseModel):
    id: int
    name: str | None = None
    type: str
    url: str | None = None

    class Config:
        from_attributes = True


class PublishTaskResponse(BaseModel):
    id: int
    title: str
    content: str | None
    comment_guide: str | None = None
    topic: str | None = None
    cover_text: str | None = None
    wizard_step: int | None = None
    tags: list[str] | None
    platform: str
    account_id: int
    content_type: str
    material_ids: list[int] | None
    publish_time: datetime | None
    status: str
    error_message: str | None
    created_at: datetime
    materials: list[MaterialSummary] | None = None

    @field_serializer("publish_time", "created_at")
    def serialize_datetimes(self, value: datetime | None) -> str | None:
        return format_utc_datetime(value)

    class Config:
        from_attributes = True


class PublishTaskLogResponse(BaseModel):
    id: int
    task_id: int
    step: str
    status: str
    message: str | None
    created_at: datetime

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime) -> str:
        return format_utc_datetime(value) or ""

    class Config:
        from_attributes = True
