from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AiGenerationRecord, Material, PlatformAccount, PublishTask
from app.services.risk_stats_service import RiskStatsService
from app.utils.failure_classifier import classify_failure_message


class DashboardService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_summary(self) -> dict:
        task_rows = (
            self.db.query(PublishTask.status, func.count(PublishTask.id))
            .group_by(PublishTask.status)
            .all()
        )
        task_counts = {status: count for status, count in task_rows}

        account_rows = (
            self.db.query(PlatformAccount.status, func.count(PlatformAccount.id))
            .group_by(PlatformAccount.status)
            .all()
        )
        account_counts = {status: count for status, count in account_rows}

        failed_tasks = (
            self.db.query(PublishTask)
            .filter(PublishTask.status == "failed")
            .order_by(PublishTask.updated_at.desc())
            .limit(10)
            .all()
        )

        unhealthy_accounts = (
            self.db.query(PlatformAccount)
            .filter(PlatformAccount.status.in_(["inactive", "expired"]))
            .order_by(PlatformAccount.updated_at.desc())
            .limit(10)
            .all()
        )

        since = datetime.utcnow() - timedelta(days=7)
        ai_rows = (
            self.db.query(
                AiGenerationRecord.type,
                func.count(AiGenerationRecord.id),
                func.coalesce(func.sum(AiGenerationRecord.cost), 0),
            )
            .filter(AiGenerationRecord.created_at >= since)
            .group_by(AiGenerationRecord.type)
            .all()
        )
        ai_by_type = {
            row[0]: {"count": int(row[1]), "cost": float(row[2])}
            for row in ai_rows
        }

        provider_rows = (
            self.db.query(
                AiGenerationRecord.provider,
                func.count(AiGenerationRecord.id),
            )
            .filter(AiGenerationRecord.created_at >= since)
            .group_by(AiGenerationRecord.provider)
            .order_by(func.count(AiGenerationRecord.id).desc())
            .limit(8)
            .all()
        )

        total_ai = self.db.query(func.count(AiGenerationRecord.id)).scalar() or 0
        text_tokens_total = (
            self.db.query(func.coalesce(func.sum(AiGenerationRecord.cost), 0))
            .filter(AiGenerationRecord.type == "text")
            .scalar()
            or 0
        )
        image_units_total = (
            self.db.query(func.coalesce(func.sum(AiGenerationRecord.cost), 0))
            .filter(AiGenerationRecord.type == "image")
            .scalar()
            or 0
        )

        settings = get_settings()
        alerts: list[dict] = []
        expired_count = account_counts.get("expired", 0)
        if expired_count:
            alerts.append(
                {
                    "id": "expired_accounts",
                    "level": "warning",
                    "message": f"{expired_count} 个平台账号 Cookie 已过期，请尽快重新登录",
                    "link": "/accounts",
                }
            )
        failed_count = task_counts.get("failed", 0)
        if failed_count >= settings.dashboard_failed_task_alert_threshold:
            alerts.append(
                {
                    "id": "failed_tasks",
                    "level": "error",
                    "message": f"{failed_count} 条发布任务失败，请检查日志或重试",
                    "link": "/tasks?status=failed",
                }
            )

        risk_stats = RiskStatsService(self.db).get_stats(days=7)
        if risk_stats["failed_risk"] >= 3:
            alerts.append(
                {
                    "id": "risk_failures",
                    "level": "warning",
                    "message": (
                        f"近 7 天有 {risk_stats['failed_risk']} 条疑似平台风控失败，"
                        "建议查看试运行记录并评估发布策略"
                    ),
                    "link": "/tasks?status=failed",
                }
            )
        if risk_stats["rate_limit_blocks"] >= 10:
            alerts.append(
                {
                    "id": "rate_limit_blocks",
                    "level": "warning",
                    "message": (
                        f"近 7 天限频拦截 {risk_stats['rate_limit_blocks']} 次，"
                        "可在系统设置调整间隔或日上限"
                    ),
                    "link": "/settings",
                }
            )

        return {
            "alerts": alerts,
            "risk_stats": risk_stats,
            "task_trends": self._task_trends(),
            "overview": {
                "accounts": self.db.query(func.count(PlatformAccount.id)).scalar() or 0,
                "materials": self.db.query(func.count(Material.id)).scalar() or 0,
                "tasks": sum(task_counts.values()),
                "success_tasks": task_counts.get("success", 0),
                "failed_tasks": task_counts.get("failed", 0),
                "pending_tasks": task_counts.get("pending", 0),
            },
            "task_counts": task_counts,
            "account_health": {
                "active": account_counts.get("active", 0),
                "inactive": account_counts.get("inactive", 0),
                "expired": account_counts.get("expired", 0),
                "unhealthy_accounts": [
                    {
                        "id": a.id,
                        "platform": a.platform,
                        "account_name": a.account_name,
                        "status": a.status,
                    }
                    for a in unhealthy_accounts
                ],
            },
            "failed_tasks": [
                {
                    "id": t.id,
                    "title": t.title,
                    "platform": t.platform,
                    "error_message": t.error_message,
                    "failure_category": classify_failure_message(t.error_message),
                    "updated_at": t.updated_at,
                }
                for t in failed_tasks
            ],
            "ai_stats": {
                "total_calls": int(total_ai),
                "text_tokens_total": float(text_tokens_total),
                "image_units_total": float(image_units_total),
                "last_7_days": ai_by_type,
                "by_provider": [
                    {"provider": row[0], "count": int(row[1])}
                    for row in provider_rows
                ],
            },
        }

    def _task_trends(self) -> dict:
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        since = today - timedelta(days=6)

        platform_rows = (
            self.db.query(PublishTask.platform, func.count(PublishTask.id))
            .group_by(PublishTask.platform)
            .order_by(func.count(PublishTask.id).desc())
            .all()
        )

        daily_rows = (
            self.db.query(
                func.date(PublishTask.created_at),
                PublishTask.status,
                func.count(PublishTask.id),
            )
            .filter(PublishTask.created_at >= since)
            .group_by(func.date(PublishTask.created_at), PublishTask.status)
            .all()
        )

        pending_statuses = {"pending", "pending_review", "dispatching", "running", "draft"}
        daily_map: dict[str, dict[str, int]] = {}
        for day_value, status, count in daily_rows:
            day_key = str(day_value)
            bucket = daily_map.setdefault(
                day_key,
                {"success": 0, "failed": 0, "pending": 0, "other": 0},
            )
            if status == "success":
                bucket["success"] += int(count)
            elif status == "failed":
                bucket["failed"] += int(count)
            elif status in pending_statuses:
                bucket["pending"] += int(count)
            else:
                bucket["other"] += int(count)

        daily_7d: list[dict] = []
        for offset in range(7):
            day = today + timedelta(days=offset - 6)
            day_key = day.strftime("%Y-%m-%d")
            stats = daily_map.get(day_key, {"success": 0, "failed": 0, "pending": 0, "other": 0})
            daily_7d.append({"date": day_key, **stats})

        return {
            "by_platform": [
                {"platform": platform or "unknown", "count": int(count)}
                for platform, count in platform_rows
            ],
            "daily_7d": daily_7d,
        }
