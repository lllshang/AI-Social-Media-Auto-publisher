from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import PublishTask
from app.workers.redis_queue import task_queue


class MetricsService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()

    def prometheus_text(self) -> str:
        lines: list[str] = []
        rows = (
            self.db.query(PublishTask.status, func.count(PublishTask.id))
            .group_by(PublishTask.status)
            .all()
        )
        lines.append("# HELP ai_publish_tasks_total Publish tasks by status")
        lines.append("# TYPE ai_publish_tasks_total gauge")
        for status, count in rows:
            lines.append(f'ai_publish_tasks_total{{status="{status}"}} {int(count)}')

        depth = task_queue.queue_depth() if self.settings.task_queue_enabled else 0
        lines.append("# HELP ai_publish_queue_depth Redis execute queue length")
        lines.append("# TYPE ai_publish_queue_depth gauge")
        lines.append(f"ai_publish_queue_depth {depth}")
        return "\n".join(lines) + "\n"
