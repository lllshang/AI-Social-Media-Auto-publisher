from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import PublishTask, PublishTaskLog
from app.utils.failure_classifier import classify_failure_message


class RiskStatsService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_stats(self, *, days: int = 7) -> dict:
        since = datetime.utcnow() - timedelta(days=days)

        sensitive_word_blocks = (
            self.db.query(func.count(PublishTaskLog.id))
            .filter(
                PublishTaskLog.step == "sensitive_word",
                PublishTaskLog.created_at >= since,
            )
            .scalar()
            or 0
        )
        rate_limit_blocks = (
            self.db.query(func.count(PublishTaskLog.id))
            .filter(
                PublishTaskLog.step == "rate_limit",
                PublishTaskLog.created_at >= since,
            )
            .scalar()
            or 0
        )

        finished_tasks = (
            self.db.query(PublishTask)
            .filter(
                PublishTask.status.in_(["success", "failed"]),
                PublishTask.updated_at >= since,
            )
            .all()
        )

        success_count = sum(1 for task in finished_tasks if task.status == "success")
        failed_count = sum(1 for task in finished_tasks if task.status == "failed")
        total_finished = success_count + failed_count
        failure_rate = (
            round(failed_count / total_finished * 100, 1) if total_finished else 0.0
        )

        failed_risk = 0
        failed_technical = 0
        failed_other = 0
        for task in finished_tasks:
            if task.status != "failed":
                continue
            category = classify_failure_message(task.error_message)
            if category == "risk":
                failed_risk += 1
            elif category == "technical":
                failed_technical += 1
            else:
                failed_other += 1

        return {
            "period_days": days,
            "sensitive_word_blocks": int(sensitive_word_blocks),
            "rate_limit_blocks": int(rate_limit_blocks),
            "success_count": success_count,
            "failed_count": failed_count,
            "failure_rate_percent": failure_rate,
            "failed_risk": failed_risk,
            "failed_technical": failed_technical,
            "failed_other": failed_other,
        }
