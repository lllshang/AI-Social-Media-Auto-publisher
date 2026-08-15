import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.material_cleanup_service import MaterialCleanupService
from app.services.publish_service import PublishService
from app.services.system_config_service import SystemConfigService
from app.workers.redis_queue import task_queue


class ScheduleWorker:
    def __init__(self) -> None:
        self._scheduler: AsyncIOScheduler | None = None

    def start(self) -> AsyncIOScheduler | None:
        db = SessionLocal()
        try:
            config = SystemConfigService(db)
            scheduler_enabled = config.scheduler_enabled()
            auto_retry_enabled = config.auto_retry_enabled()
            cleanup_enabled = config.material_cleanup_enabled()
            poll_interval = config.scheduler_poll_interval_seconds()
            from app.services.trending_config_service import TrendingConfigService

            trending_cfg = TrendingConfigService(db)
            trending_enabled = trending_cfg.enabled()
            trending_cron_hour = trending_cfg.fetch_cron_hour()
        finally:
            db.close()

        if not (scheduler_enabled or auto_retry_enabled or cleanup_enabled or trending_enabled):
            logger.info("后台调度已全部关闭（定时发布/自动重试/素材清理/热点）")
            return None

        scheduler = AsyncIOScheduler()
        if scheduler_enabled:
            scheduler.add_job(
                self.poll_due_tasks,
                "interval",
                seconds=poll_interval,
                id="publish_schedule_poll",
                replace_existing=True,
                max_instances=1,
            )
        if auto_retry_enabled:
            scheduler.add_job(
                self.poll_auto_retries,
                "interval",
                seconds=poll_interval,
                id="publish_auto_retry_poll",
                replace_existing=True,
                max_instances=1,
            )
        if cleanup_enabled:
            scheduler.add_job(
                self.run_material_cleanup,
                "interval",
                hours=1,
                id="material_cleanup",
                replace_existing=True,
                max_instances=1,
            )
        if trending_enabled:
            scheduler.add_job(
                self.run_trending_fetch,
                "cron",
                hour=trending_cron_hour,
                minute=0,
                id="trending_fetch_daily",
                replace_existing=True,
                max_instances=1,
            )
        scheduler.start()
        self._scheduler = scheduler
        logger.info(
            "后台调度已启动：定时发布={} 自动重试={} 素材清理={} 热点抓取={}，轮询间隔 {} 秒",
            scheduler_enabled,
            auto_retry_enabled,
            cleanup_enabled,
            trending_enabled,
            poll_interval,
        )
        return scheduler

    def shutdown(self) -> None:
        if self._scheduler:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
            logger.info("后台调度已停止")

    async def poll_due_tasks(self) -> None:
        db = SessionLocal()
        try:
            PublishService(db).recover_stuck_running_tasks()
            task_id = self._claim_due_task(db)
            if task_id is None:
                return
            logger.info("定时触发发布任务 #{}，入队执行", task_id)
            await asyncio.to_thread(task_queue.enqueue_execute, task_id)
        except Exception as exc:
            logger.exception("定时发布轮询失败: {}", exc)
        finally:
            db.close()

    async def poll_auto_retries(self) -> None:
        db = SessionLocal()
        try:
            service = PublishService(db)
            service.recover_stuck_running_tasks()
            if service.rate_limit.is_globally_saturated():
                return
            task_id = service.claim_auto_retry_task()
            if task_id is None:
                return
            if not service.try_start_execution(task_id):
                return
            logger.info("自动重试发布任务 #{}，入队执行", task_id)
            await asyncio.to_thread(task_queue.enqueue_execute, task_id)
        except Exception as exc:
            logger.exception("自动重试轮询失败: {}", exc)
        finally:
            db.close()

    async def run_material_cleanup(self) -> None:
        db = SessionLocal()
        try:
            service = MaterialCleanupService(db)
            result = service.run_cleanup()
            if result["removed"]:
                logger.info("素材清理：移除 {} 条，跳过 {}", result["removed"], result["skipped"])
        except Exception as exc:
            logger.exception("素材清理失败: {}", exc)
        finally:
            db.close()

    async def run_trending_fetch(self) -> None:
        db = SessionLocal()
        try:
            from app.services.trending_fetch_service import TrendingFetchService

            service = TrendingFetchService(db)
            run = await service.fetch_all()
            logger.info(
                "热点定时抓取完成 status={} source={} items={}",
                run.status,
                run.source,
                run.item_count,
            )
        except Exception as exc:
            logger.exception("热点定时抓取失败: {}", exc)
        finally:
            db.close()

    def _claim_due_task(self, db: Session) -> int | None:
        service = PublishService(db)
        for task in service.list_due_pending_tasks():
            if service.try_start_execution(task.id):
                return task.id
        return None


schedule_worker = ScheduleWorker()
