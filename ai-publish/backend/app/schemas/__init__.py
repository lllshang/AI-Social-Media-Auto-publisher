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


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role_name: str
    permissions: list[str]


class LoginRequest(BaseModel):
    username: str
    password: str


class PlatformAccountCreate(BaseModel):
    platform: str = "xhs"
    account_name: str


class PlatformAccountUpdate(BaseModel):
    account_name: str | None = None
    remark: str | None = None


class PlatformAccountResponse(BaseModel):
    id: int
    platform: str
    account_name: str
    remark: str | None = None
    group_id: int | None = None
    group_name: str | None = None
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
    content_type: str = "note"
    style: str = "default"


class ImageGenerateRequest(BaseModel):
    topic: str
    platform: str = "xhs"
    ratio: str = "3:4"
    style: str = "default"
    count: int = Field(default=1, ge=1, le=4)
    cover_text: str | None = None
    brand_color: str | None = None
    brand_hint: str | None = None


class TextMaterialCreate(BaseModel):
    title: str
    content: str
    tags: list[str] | None = None
    platform: str = "xhs"
    comment_guide: str | None = None
    topic: str | None = None
    category: str | None = None
    ai_record_id: int | None = None


class MaterialResponse(BaseModel):
    id: int
    type: str
    source: str
    name: str | None = None
    category: str | None = None
    file_path: str
    url: str | None
    thumbnail_url: str | None = None
    text_preview: str | None = None
    text_content: str | None = None
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
    bilibili_tid: int | None = None
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
    bilibili_tid: int | None = None


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
    bilibili_tid: int | None = None
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


class ReviewPendingListResponse(BaseModel):
    items: list[PublishTaskResponse]
    total: int
    page: int
    page_size: int


class ReviewHistoryItem(BaseModel):
    id: int
    task_id: int
    task_title: str
    platform: str
    action: str
    comment: str | None = None
    reviewer_id: int | None = None
    reviewer_name: str | None = None
    created_at: datetime

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime) -> str:
        return format_utc_datetime(value) or ""

    class Config:
        from_attributes = True


class ReviewHistoryListResponse(BaseModel):
    items: list[ReviewHistoryItem]
    total: int
    page: int
    page_size: int


class DashboardFailedTask(BaseModel):
    id: int
    title: str
    platform: str
    error_message: str | None = None
    updated_at: datetime

    @field_serializer("updated_at")
    def serialize_updated_at(self, value: datetime) -> str:
        return format_utc_datetime(value) or ""


class DashboardUnhealthyAccount(BaseModel):
    id: int
    platform: str
    account_name: str
    status: str


class DashboardOverview(BaseModel):
    accounts: int
    materials: int
    tasks: int
    success_tasks: int
    failed_tasks: int
    pending_tasks: int


class DashboardAccountHealth(BaseModel):
    active: int
    inactive: int
    expired: int
    unhealthy_accounts: list[DashboardUnhealthyAccount]


class DashboardAiTypeStat(BaseModel):
    count: int
    cost: float


class DashboardAiProviderStat(BaseModel):
    provider: str
    count: int


class DashboardAiStats(BaseModel):
    total_calls: int
    text_tokens_total: float = 0
    image_units_total: float = 0
    last_7_days: dict[str, DashboardAiTypeStat]
    by_provider: list[DashboardAiProviderStat]


class DashboardAlert(BaseModel):
    id: str
    level: str
    message: str
    link: str


class DashboardTaskPlatformStat(BaseModel):
    platform: str
    count: int


class DashboardTaskDailyStat(BaseModel):
    date: str
    success: int = 0
    failed: int = 0
    pending: int = 0
    other: int = 0


class DashboardTaskTrends(BaseModel):
    by_platform: list[DashboardTaskPlatformStat] = []
    daily_7d: list[DashboardTaskDailyStat] = []


class DashboardSummaryResponse(BaseModel):
    alerts: list[DashboardAlert] = []
    overview: DashboardOverview
    task_counts: dict[str, int]
    task_trends: DashboardTaskTrends
    account_health: DashboardAccountHealth
    failed_tasks: list[DashboardFailedTask]
    ai_stats: DashboardAiStats


class ContentTemplateCreate(BaseModel):
    name: str
    industry: str
    topic: str
    platform: str | None = None
    content_type: str = "note"
    template_kind: str = "text"
    title_hint: str | None = None
    content_body: str | None = None
    tags: list[str] | None = None
    image_style: str | None = None
    image_ratio: str | None = None
    brand_color: str | None = None
    brand_hint: str | None = None
    status: str = "active"


class ContentTemplateUpdate(BaseModel):
    name: str | None = None
    industry: str | None = None
    platform: str | None = None
    content_type: str | None = None
    template_kind: str | None = None
    topic: str | None = None
    title_hint: str | None = None
    content_body: str | None = None
    tags: list[str] | None = None
    image_style: str | None = None
    image_ratio: str | None = None
    brand_color: str | None = None
    brand_hint: str | None = None
    status: str | None = None


class ContentTemplateResponse(BaseModel):
    id: int
    name: str
    industry: str
    platform: str | None = None
    content_type: str
    template_kind: str
    topic: str
    title_hint: str | None = None
    content_body: str | None = None
    tags: list[str] | None = None
    image_style: str | None = None
    image_ratio: str | None = None
    brand_color: str | None = None
    brand_hint: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at")
    def serialize_datetime(self, value: datetime) -> str:
        return format_utc_datetime(value) or ""


class AccountGroupCreate(BaseModel):
    name: str
    remark: str | None = None


class AccountGroupUpdate(BaseModel):
    name: str | None = None
    remark: str | None = None


class AccountGroupResponse(BaseModel):
    id: int
    name: str
    remark: str | None = None
    account_count: int = 0
    created_at: datetime

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime) -> str:
        return format_utc_datetime(value) or ""


class AccountGroupAssignRequest(BaseModel):
    group_id: int | None = None


class PromptBuildRequest(BaseModel):
    kind: str = Field(description="text 或 image")
    platform: str = "xhs"
    topic: str
    content_type: str = "note"
    ratio: str = "3:4"
    style: str = "default"
    cover_text: str | None = None
    brand_color: str | None = None
    brand_hint: str | None = None


class PromptBuildResponse(BaseModel):
    kind: str
    platform: str
    template_name: str
    prompt: str
    prompt_zh: str
    prompt_en: str | None = None
    negative_prompt: str | None = None


class AiGenerationRecordResponse(BaseModel):
    id: int
    type: str
    provider: str
    prompt: str
    result_summary: str | None = None
    cost: float
    created_by: int | None = None
    created_at: datetime

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime) -> str:
        return format_utc_datetime(value) or ""

    class Config:
        from_attributes = True


class SystemConfigResponse(BaseModel):
    id: int
    config_key: str
    config_value: str | None = None
    remark: str | None = None
    updated_at: datetime

    @field_serializer("updated_at")
    def serialize_updated_at(self, value: datetime) -> str:
        return format_utc_datetime(value) or ""

    class Config:
        from_attributes = True


class RoleUserBrief(BaseModel):
    username: str
    initial_password: str | None = None


class RoleResponse(BaseModel):
    id: int
    role_name: str
    permissions: list[str] | None = None
    users: list[RoleUserBrief] = Field(default_factory=list)
    created_at: datetime

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime) -> str:
        return format_utc_datetime(value) or ""

    class Config:
        from_attributes = True


class UserCreateRequest(BaseModel):
    username: str
    password: str
    role_id: int | None = None


class UserUpdateRequest(BaseModel):
    role_id: int | None = None
    status: str | None = None


class UserResetPasswordRequest(BaseModel):
    new_password: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class UserResponse(BaseModel):
    id: int
    username: str
    role_id: int | None = None
    role_name: str = ""
    status: str
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at")
    def serialize_dt(self, value: datetime) -> str:
        return format_utc_datetime(value) or ""

    class Config:
        from_attributes = True


class OperationLogResponse(BaseModel):
    id: int
    user_id: int | None = None
    action: str
    target_type: str | None = None
    target_id: int | None = None
    ip: str | None = None
    created_at: datetime

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime) -> str:
        return format_utc_datetime(value) or ""

    class Config:
        from_attributes = True
