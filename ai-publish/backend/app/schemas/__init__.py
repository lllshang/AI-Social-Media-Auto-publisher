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
    worker_id: int | None = None
    publish_proxy: str | None = None
    clear_publish_proxy: bool = False


class PlatformAccountResponse(BaseModel):
    id: int
    platform: str
    account_name: str
    remark: str | None = None
    group_id: int | None = None
    group_name: str | None = None
    worker_id: int | None = None
    worker_name: str | None = None
    publish_proxy_masked: str | None = None
    has_publish_proxy: bool = False
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


class VideoGenerateRequest(BaseModel):
    topic: str
    platform: str = "douyin"
    duration: int = Field(default=5, ge=5, le=10)
    resolution: str = "720p"
    fps: int = Field(default=24, ge=24, le=30)
    style: str = "default"
    image_url: str | None = None
    count: int = 1
    avatar_id: int | None = None
    avatar_type: str | None = None  # digital_human | simulation_human


class AvatarCreate(BaseModel):
    name: str
    type: str  # digital_human | simulation_human
    gender: str | None = None
    config: dict | None = None
    reference_images: list[int] | None = None  # material IDs


class AvatarUpdate(BaseModel):
    name: str | None = None
    gender: str | None = None
    config: dict | None = None
    reference_images: list[int] | None = None
    thumbnail: str | None = None
    status: str | None = None


class AvatarResponse(BaseModel):
    id: int
    name: str
    type: str
    gender: str | None = None
    config: dict | None = None
    reference_images: list | None = None
    thumbnail_url: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at")
    def serialize_datetime(self, value: datetime) -> str:
        return format_utc_datetime(value) or ""

    class Config:
        from_attributes = True


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
    moderation_status: str | None = None
    moderation_detail: str | None = None
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
    account_name: str | None = None
    worker_name: str | None = None
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
    failure_category: str = "other"
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


class DashboardRiskStats(BaseModel):
    period_days: int = 7
    sensitive_word_blocks: int = 0
    rate_limit_blocks: int = 0
    success_count: int = 0
    failed_count: int = 0
    failure_rate_percent: float = 0
    failed_risk: int = 0
    failed_technical: int = 0
    failed_other: int = 0


class DashboardSummaryResponse(BaseModel):
    alerts: list[DashboardAlert] = []
    risk_stats: DashboardRiskStats
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


class SensitiveWordCreate(BaseModel):
    word: str
    remark: str | None = None


class SensitiveWordBatchCreate(BaseModel):
    words: list[str]


class SensitiveWordResponse(BaseModel):
    id: int
    word: str
    enabled: bool
    remark: str | None = None
    created_at: datetime

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime) -> str:
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


class PublishWorkerCreate(BaseModel):
    name: str


class PublishWorkerResponse(BaseModel):
    id: int
    name: str
    worker_key: str
    hostname: str | None = None
    online: bool = False
    status: str
    last_heartbeat_at: datetime | None = None
    created_at: datetime

    @field_serializer("last_heartbeat_at", "created_at")
    def serialize_dt(self, value: datetime | None) -> str | None:
        return format_utc_datetime(value)


class PublishWorkerCreateResponse(PublishWorkerResponse):
    token: str


class PublishWorkerRotateTokenResponse(PublishWorkerResponse):
    token: str


class PublishWorkerHeartbeatRequest(BaseModel):
    hostname: str | None = None


class PublishWorkerClaimRequest(BaseModel):
    hostname: str | None = None
    timeout_seconds: int = 30


class PublishWorkerClaimResponse(BaseModel):
    task: dict | None = None


class WorkerTaskLogRequest(BaseModel):
    step: str
    status: str
    message: str | None = None


class WorkerTaskFinishRequest(BaseModel):
    success: bool
    message: str


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


class TrendingItemResponse(BaseModel):
    id: int
    platform: str
    title: str
    tags: list[str] = []
    source_url: str | None = None
    cover_url: str | None = None
    video_url: str | None = None
    heat_score: float = 0
    rank: int | None = None
    appear_days: int = 1
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    snapshot_date: str | None = None


class TrendingStatusResponse(BaseModel):
    enabled: bool
    fetch_mode: str
    paid_api_enabled: bool
    last_item_at: str | None = None
    last_fetch_at: str | None = None
    last_fetch_source: str | None = None
    last_fetch_status: str | None = None
    stale: bool = False


class TrendingFetchResponse(BaseModel):
    id: int
    source: str
    mode: str
    status: str
    item_count: int
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None

    @field_serializer("started_at", "finished_at")
    def serialize_dt(self, value: datetime | None) -> str | None:
        return format_utc_datetime(value) if value else None


class TrendingAiRecommendRequest(BaseModel):
    period: str = "daily"
    platform: str | None = None
    category: str | None = None
    limit: int = 5


class TrendingRecommendation(BaseModel):
    topic: str
    platform: str
    content_type: str = "video"
    reason: str = ""
    reference_trend_ids: list[int] = []


class TrendingAiRecommendResponse(BaseModel):
    recommendations: list[TrendingRecommendation]
    provider: str | None = None
    message: str | None = None


class TrendingWorkerIngestItem(BaseModel):
    platform: str
    rank: int = 0
    title: str
    heat_score: float = 0
    source_url: str | None = None
    cover_url: str | None = None
    video_url: str | None = None
    tags: list[str] = []


class TrendingWorkerIngestRequest(BaseModel):
    items: list[TrendingWorkerIngestItem]


# ── Creative Session (内容创作) ───────────────────────────────

class CreativeSessionCreate(BaseModel):
    content_type: str  # video | note
    keywords: str
    background: str | None = None
    theme_style: str | None = None
    scene_desc: str | None = None
    platforms: list[str] | None = None


class PolishRequest(BaseModel):
    message: str | None = None  # 用户自然语言指令
    quick_action: str | None = None  # shorten | expand | humorous | add_emoji | formal | bilibili_style | xiaohongshu_style | douyin_style


class PolishResponse(BaseModel):
    title: str
    body: str
    tags: list[str] = []


class CopyResponse(BaseModel):
    title: str
    body: str
    tags: list[str] = []


class CopyUpdateRequest(BaseModel):
    title: str | None = None
    body: str | None = None
    tags: list[str] | None = None


class GenerationRequest(BaseModel):
    gen_type: str  # text_to_video | image_to_video | simulation_human | digital_human | cover | images
    description: str | None = None  # 覆盖默认的视频描述
    duration: int = Field(default=5, ge=5, le=10)
    resolution: str = "720p"
    fps: int = Field(default=24, ge=24, le=30)
    image_url: str | None = None  # 图生视频/仿真人参考图
    avatar_id: int | None = None
    avatar_type: str | None = None
    style: str = "default"  # 图文风格
    cover_text: str | None = None
    brand_color: str | None = None
    brand_hint: str | None = None
    count: int = Field(default=1, ge=1, le=9)  # 图文数量


class GenerationTaskResponse(BaseModel):
    id: int
    session_id: int
    gen_type: str
    provider: str
    status: str
    progress: int
    result: dict | None = None
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None

    @field_serializer("created_at", "completed_at")
    def serialize_dt(self, value: datetime | None) -> str | None:
        return format_utc_datetime(value)

    class Config:
        from_attributes = True


class CreativeSessionResponse(BaseModel):
    id: int
    user_id: int
    content_type: str
    keywords: str
    background: str | None = None
    theme_style: str | None = None
    scene_desc: str | None = None
    platforms: list[str] | None = None
    status: str
    final_copy: dict | None = None
    polish_history: list | None = None
    output_material_ids: list[int] | None = None
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at")
    def serialize_dt(self, value: datetime) -> str:
        return format_utc_datetime(value) or ""

    class Config:
        from_attributes = True


class CreativeSessionListResponse(BaseModel):
    items: list[CreativeSessionResponse]
    total: int
    page: int
    page_size: int
