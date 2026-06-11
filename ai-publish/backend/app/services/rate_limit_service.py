from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import PublishTask
from app.services.system_config_service import SystemConfigService


@dataclass
class RateLimitCheckResult:
    allowed: bool
    message: str = ""


class RateLimitService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.config = SystemConfigService(db)

    def enabled(self) -> bool:
        return self.config.rate_limit_enabled()

    def running_count(self, *, exclude_task_id: int | None = None) -> int:
        query = self.db.query(PublishTask).filter(PublishTask.status == "running")
        if exclude_task_id is not None:
            query = query.filter(PublishTask.id != exclude_task_id)
        return query.count()

    def is_globally_saturated(self) -> bool:
        if not self.enabled():
            return False
        max_concurrent = self.config.rate_limit_max_concurrent()
        return self.running_count() >= max_concurrent

    def evaluate(self, task: PublishTask, *, exclude_task_id: int | None = None) -> RateLimitCheckResult:
        if not self.enabled():
            return RateLimitCheckResult(allowed=True)

        max_concurrent = self.config.rate_limit_max_concurrent()
        running = self.running_count(exclude_task_id=exclude_task_id)
        if running >= max_concurrent:
            return RateLimitCheckResult(
                allowed=False,
                message=f"发布并发已满（{running}/{max_concurrent}），请稍后再试",
            )

        account_id = task.account_id
        if not account_id:
            return RateLimitCheckResult(allowed=True)

        min_interval = self.config.rate_limit_min_interval_seconds()
        if min_interval > 0:
            last_success = (
                self.db.query(PublishTask)
                .filter(
                    PublishTask.account_id == account_id,
                    PublishTask.status == "success",
                )
                .order_by(PublishTask.updated_at.desc())
                .first()
            )
            if last_success and last_success.updated_at:
                elapsed = (datetime.utcnow() - last_success.updated_at).total_seconds()
                if elapsed < min_interval:
                    wait_seconds = int(min_interval - elapsed) + 1
                    return RateLimitCheckResult(
                        allowed=False,
                        message=f"同账号发布间隔不足，请约 {wait_seconds} 秒后再试",
                    )

        daily_max = self.config.rate_limit_daily_per_account()
        skip_daily = (
            not self.config.rate_limit_include_retry()
            and (task.retry_count or 0) > 0
        )
        if daily_max > 0 and not skip_daily:
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            success_today = (
                self.db.query(PublishTask)
                .filter(
                    PublishTask.account_id == account_id,
                    PublishTask.status == "success",
                    PublishTask.updated_at >= today_start,
                )
                .count()
            )
            if success_today >= daily_max:
                return RateLimitCheckResult(
                    allowed=False,
                    message=f"该账号今日发布已达上限（{daily_max} 条）",
                )

        return RateLimitCheckResult(allowed=True)
