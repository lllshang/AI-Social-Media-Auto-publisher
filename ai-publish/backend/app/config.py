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

    database_url: str = "sqlite:///./data/aipublish.db"
    redis_url: str = "redis://127.0.0.1:6380/0"

    cookie_encryption_key: str = "dev-cookie-key-change-in-prod"
    storage: str = "local"
    storage_local_path: str = "./data/materials"
    cookie_dir: str = "./data/cookies"

    ai_text_provider: str = "auto"
    ai_text_model: str = ""
    ai_image_provider: str = "auto"
    ai_image_model: str = ""
    default_platform: str = "xhs"
    require_content_review: bool = False

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
    minimax_base_url: str = "https://api.minimax.chat/v1"

    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_text_model: str = ""

    playwright_headless: bool = False
    playwright_channel: str = "chrome"
    login_timeout_seconds: int = 120

    sau_vendor_path: str = "../../vendor/social-auto-upload"
    web_dist_path: str = ""

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
