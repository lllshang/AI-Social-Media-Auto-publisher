from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import SystemConfig


class SystemConfigService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()

    def list_configs(self) -> list[SystemConfig]:
        return self.db.query(SystemConfig).order_by(SystemConfig.config_key.asc()).all()

    def get_value(self, key: str, default: str | None = None) -> str | None:
        row = self.db.query(SystemConfig).filter(SystemConfig.config_key == key).first()
        if row and row.config_value is not None:
            return row.config_value
        return default

    def get_bool(self, key: str, default: bool = False) -> bool:
        raw = self.get_value(key)
        if raw is None:
            return default
        return raw.strip().lower() in {"1", "true", "yes", "on"}

    def get_int(self, key: str, default: int) -> int:
        raw = self.get_value(key)
        if raw is None:
            return default
        try:
            return int(raw)
        except ValueError:
            return default

    def set_value(self, key: str, value: str | None, remark: str | None = None) -> SystemConfig:
        row = self.db.query(SystemConfig).filter(SystemConfig.config_key == key).first()
        if row:
            row.config_value = value
            if remark is not None:
                row.remark = remark
        else:
            row = SystemConfig(config_key=key, config_value=value, remark=remark)
            self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def require_content_review(self) -> bool:
        db_value = self.get_value("require_content_review")
        if db_value is not None:
            return self.get_bool("require_content_review", False)
        return self.settings.require_content_review

    def scheduler_enabled(self) -> bool:
        db_value = self.get_value("scheduler_enabled")
        if db_value is not None:
            return self.get_bool("scheduler_enabled", True)
        return self.settings.scheduler_enabled

    def scheduler_poll_interval_seconds(self) -> int:
        db_value = self.get_value("scheduler_poll_interval_seconds")
        if db_value is not None:
            return self.get_int("scheduler_poll_interval_seconds", self.settings.scheduler_poll_interval_seconds)
        return self.settings.scheduler_poll_interval_seconds


def ensure_default_system_configs(db: Session) -> None:
    defaults = [
        ("require_content_review", "false", "提交后是否进入待审核"),
        ("scheduler_enabled", "true", "是否启用定时发布调度"),
        ("scheduler_poll_interval_seconds", "30", "定时发布轮询间隔（秒）"),
        ("storage_public_base_url", "", "对象存储公网访问前缀（COS/OSS 时填写）"),
    ]
    service = SystemConfigService(db)
    for key, value, remark in defaults:
        if service.get_value(key) is None:
            service.set_value(key, value, remark)
