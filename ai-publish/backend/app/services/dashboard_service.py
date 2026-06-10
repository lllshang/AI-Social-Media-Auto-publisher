from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import AiGenerationRecord, Material, PlatformAccount, PublishTask


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

        return {
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
