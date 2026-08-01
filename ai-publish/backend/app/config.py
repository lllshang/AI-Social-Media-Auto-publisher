from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ENV = BACKEND_DIR.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=[str(PROJECT_ENV), str(BACKEND_DIR / ".env"), ".env"],
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "ai-publish"
    debug: bool = True
    secret_key: str = "change-me"
    access_token_expire_minutes: int = 1440

    admin_username: str = "admin"
    admin_password: str = "admin123"
    operator_username: str = "operator"
    operator_password: str = "operator123"
    viewer_username: str = "viewer"
    viewer_password: str = "viewer123"
    reviewer_username: str = "reviewer"
    reviewer_password: str = "reviewer123"

    database_url: str = "sqlite:///./data/aipublish.db"
    redis_url: str = "redis://127.0.0.1:6380/0"
    task_queue_enabled: bool = True
    task_queue_embedded_consumer: bool = True

    cookie_encryption_key: str = "dev-cookie-key-change-in-prod"
    storage: str = "local"
    storage_local_path: str = "./data/materials"
    cookie_dir: str = "./data/cookies"
    object_storage_endpoint: str = ""
    object_storage_region: str = ""
    object_storage_bucket: str = ""
    object_storage_access_key: str = ""
    object_storage_secret_key: str = ""
    object_storage_public_base_url: str = ""
    object_storage_prefix: str = "materials"
    object_storage_addressing_style: str = "virtual"

    ai_text_provider: str = "auto"
    ai_text_model: str = ""
    ai_image_provider: str = "auto"
    ai_image_model: str = ""
    ai_video_provider: str = "auto"
    ai_video_model: str = ""
    default_platform: str = "xhs"
    require_content_review: bool = False
    scheduler_enabled: bool = True
    scheduler_poll_interval_seconds: int = 30
    metrics_enabled: bool = True
    dashboard_failed_task_alert_threshold: int = 3

    dashscope_api_key: str = ""
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    moonshot_api_key: str = ""
    moonshot_base_url: str = "https://api.moonshot.cn/v1"
    hunyuan_api_key: str = ""
    hunyuan_base_url: str = "https://api.hunyuan.cloud.tencent.com/v1"
    hunyuan_image_base_url: str = "https://api.cloudai.tencent.com/v1"
    tencent_vod_secret_id: str = ""
    tencent_vod_secret_key: str = ""
    tencent_vod_sub_app_id: str = "1426095670"
    tencent_vod_model: str = "Hailuo|H3"
    tencent_vod_cost_per_second: float = 0.0
    tencent_maas_api_key: str = ""
    tencent_maas_base_url: str = "https://tokenhub.tencentmaas.com/v1"
    zhipu_api_key: str = ""
    zhipu_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    doubao_api_key: str = ""
    doubao_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    baidu_api_key: str = ""
    baidu_base_url: str = "https://qianfan.baidubce.com/v2"
    siliconflow_api_key: str = ""
    siliconflow_base_url: str = "https://api.siliconflow.cn/v1"
    minimax_api_key: str = ""
    minimax_base_url: str = "https://api.minimax.io/v1"

    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_text_model: str = ""

    playwright_headless: bool = False
    playwright_channel: str = "chrome"
    login_timeout_seconds: int = 300
    login_poll_interval_seconds: int = 1

    sau_vendor_path: str = "../../vendor/social-auto-upload"
    web_dist_path: str = ""
    # B 站实验功能：默认关闭，避免 biliup 预热/登录影响 API 稳定性
    bilibili_enabled: bool = False

    def _resolve_path(self, raw_path: str) -> Path:
        path = Path(raw_path).expanduser()
        if not path.is_absolute():
            path = BACKEND_DIR / path
        return path

    @property
    def storage_path(self) -> Path:
        path = self._resolve_path(self.storage_local_path)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def cookie_path(self) -> Path:
        path = self._resolve_path(self.cookie_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def web_dist_abs_path(self) -> Path | None:
        if self.web_dist_path:
            path = self._resolve_path(self.web_dist_path)
        else:
            path = BACKEND_DIR.parent / "web" / "dist"
        return path if path.exists() else None

    @property
    def sau_vendor_abs_path(self) -> Path:
        path = self._resolve_path(self.sau_vendor_path)
        return path.resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
