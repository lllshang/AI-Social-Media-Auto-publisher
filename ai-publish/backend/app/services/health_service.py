from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.workers.redis_queue import QUEUE_KEY, task_queue


class HealthService:
    def check(self, db: Session) -> dict:
        settings = get_settings()
        db_ok = self._check_database(db)
        redis_ok = False
        queue_depth = 0
        if settings.task_queue_enabled:
            redis_ok = task_queue.ping()
            queue_depth = task_queue.queue_depth()
        else:
            redis_ok = True

        components = {
            "database": "ok" if db_ok else "error",
            "redis": "ok" if redis_ok else ("disabled" if not settings.task_queue_enabled else "error"),
        }
        healthy = db_ok and (redis_ok or not settings.task_queue_enabled)
        return {
            "status": "ok" if healthy else "degraded",
            "app": settings.app_name,
            "components": components,
            "queue_depth": queue_depth,
            "task_queue_enabled": settings.task_queue_enabled,
        }

    @staticmethod
    def _check_database(db: Session) -> bool:
        try:
            db.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
