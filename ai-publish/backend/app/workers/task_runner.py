"""后台执行发布任务（手动触发与定时调度共用）。"""


def run_execute_task(task_id: int) -> None:
    import asyncio

    from app.database import SessionLocal
    from app.services.publish_service import PublishService

    async def _run() -> None:
        db = SessionLocal()
        try:
            service = PublishService(db)
            await service.execute_task(task_id, already_running=True)
        finally:
            db.close()

    asyncio.run(_run())
