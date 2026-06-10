import asyncio
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal
from app.models import PublishTask
from app.workers.task_runner import run_execute_task


class ScheduleWorker:
    def __init__(self) -> None:
        self._scheduler: AsyncIOScheduler | None = None

    def start(self) -> AsyncIOScheduler | None:
        settings = get_settings()
        if not settings.scheduler_enabled:
            logger.info("定时发布调度已关闭（SCHEDULER_ENABLED=false）")
            return None

        scheduler = AsyncIOScheduler()
        scheduler.add_job(
            self.poll_due_tasks,
            "interval",
            seconds=settings.scheduler_poll_interval_seconds,
            id="publish_schedule_poll",
            replace_existing=True,
            max_instances=1,
        )
        scheduler.start()
        self._scheduler = scheduler
        logger.info(
            "定时发布调度已启动，轮询间隔 {} 秒",
            settings.scheduler_poll_interval_seconds,
        )
        return scheduler

    def shutdown(self) -> None:
        if self._scheduler:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
            logger.info("定时发布调度已停止")

    async def poll_due_tasks(self) -> None:
        db = SessionLocal()
        try:
            task_id = self._claim_due_task(db)
            if task_id is None:
                return
            logger.info("定时触发发布任务 #{}", task_id)
            await asyncio.to_thread(run_execute_task, task_id)
        except Exception as exc:
            logger.exception("定时发布轮询失败: {}", exc)
        finally:
            db.close()

    def _claim_due_task(self, db: Session) -> int | None:
        if self._has_running_task(db):
            return None

        now = datetime.utcnow()
        task = (
            db.query(PublishTask)
            .filter(
                PublishTask.status == "pending",
                PublishTask.publish_time.isnot(None),
                PublishTask.publish_time <= now,
            )
            .order_by(PublishTask.publish_time.asc(), PublishTask.id.asc())
            .first()
        )
        if not task:
            return None

        task.status = "running"
        task.error_message = None
        db.commit()
        return task.id

    @staticmethod
    def _has_running_task(db: Session) -> bool:
        return (
            db.query(PublishTask.id).filter(PublishTask.status == "running").first()
            is not None
        )


schedule_worker = ScheduleWorker()
