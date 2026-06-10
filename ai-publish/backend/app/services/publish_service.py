import asyncio
from datetime import datetime

from sqlalchemy.orm import Session

from app.adapters.base import PublishContext
from app.adapters.factory import get_adapter_factory
from app.config import get_settings
from app.models import Material, PublishTask, PublishTaskLog
from app.services.material_service import MaterialService
from app.services.platform_account_service import PlatformAccountService
from app.services.system_config_service import SystemConfigService
from app.workers.upload_worker import UploadWorker


class PublishService:
    VALID_TRANSITIONS = {
        "draft": {"pending", "pending_review"},
        "pending_review": {"pending", "rejected"},
        "rejected": {"draft"},
        "pending": {"running"},
        "running": {"success", "failed"},
        "failed": {"pending"},
        "success": set(),
    }

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.factory = get_adapter_factory()
        self.account_service = PlatformAccountService(db)
        self.material_service = MaterialService(db)
        self.worker = UploadWorker(db)
        self.system_config = SystemConfigService(db)

    def get_task(self, task_id: int) -> PublishTask | None:
        return self.db.query(PublishTask).filter(PublishTask.id == task_id).first()

    def get_task_materials(self, task: PublishTask) -> list[Material]:
        material_ids = task.material_ids or []
        materials: list[Material] = []
        for material_id in material_ids:
            material = self.material_service.get(material_id)
            if material:
                materials.append(material)
        return materials

    def list_tasks(
        self,
        status: str | None = None,
        platform: str | None = None,
        keyword: str | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        limit: int = 100,
    ) -> list[PublishTask]:
        query = self.db.query(PublishTask)
        if status:
            query = query.filter(PublishTask.status == status)
        if platform:
            query = query.filter(PublishTask.platform == platform)
        if keyword:
            query = query.filter(PublishTask.title.like(f"%{keyword}%"))
        if created_from:
            query = query.filter(PublishTask.created_at >= created_from)
        if created_to:
            query = query.filter(PublishTask.created_at <= created_to)
        return query.order_by(PublishTask.id.desc()).limit(limit).all()

    def create_task(
        self,
        title: str,
        content: str | None,
        tags: list[str] | None,
        platform: str,
        account_id: int,
        material_ids: list[int] | None,
        content_type: str = "note",
        publish_time: datetime | None = None,
        comment_guide: str | None = None,
        topic: str | None = None,
        cover_text: str | None = None,
        wizard_step: int | None = None,
        status: str = "draft",
        user_id: int | None = None,
    ) -> PublishTask:
        account = self.account_service.get_account(account_id)
        if not account:
            raise ValueError("账号不存在")
        if material_ids:
            self.material_service.validate_material_ids(material_ids, content_type)
        task = PublishTask(
            title=title,
            content=content,
            comment_guide=comment_guide,
            topic=topic,
            cover_text=cover_text,
            wizard_step=wizard_step,
            tags=tags or [],
            platform=platform,
            account_id=account_id,
            content_type=content_type,
            material_ids=material_ids or [],
            publish_time=publish_time,
            status=status,
            created_by=user_id,
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def update_task(
        self,
        task_id: int,
        *,
        title: str | None = None,
        content: str | None = None,
        comment_guide: str | None = None,
        topic: str | None = None,
        cover_text: str | None = None,
        wizard_step: int | None = None,
        tags: list[str] | None = None,
        account_id: int | None = None,
        material_ids: list[int] | None = None,
        publish_time: datetime | None = None,
    ) -> PublishTask:
        task = self.get_task(task_id)
        if not task:
            raise ValueError("任务不存在")
        if task.status != "draft":
            raise ValueError("仅 draft 状态任务可编辑")

        if account_id is not None:
            account = self.account_service.get_account(account_id)
            if not account:
                raise ValueError("账号不存在")
            task.account_id = account_id

        if material_ids is not None:
            if material_ids:
                self.material_service.validate_material_ids(material_ids, task.content_type)
            task.material_ids = material_ids

        if title is not None:
            task.title = title
        if content is not None:
            task.content = content
        if comment_guide is not None:
            task.comment_guide = comment_guide
        if topic is not None:
            task.topic = topic
        if cover_text is not None:
            task.cover_text = cover_text
        if wizard_step is not None:
            task.wizard_step = wizard_step
        if tags is not None:
            task.tags = tags
        if publish_time is not None:
            task.publish_time = publish_time

        self.db.commit()
        self.db.refresh(task)
        return task

    def submit_task(self, task_id: int) -> PublishTask:
        task = self.get_task(task_id)
        if not task:
            raise ValueError("任务不存在")
        if task.status not in {"draft", "failed"}:
            raise ValueError("当前状态不可提交")
        next_status = "pending_review" if self.system_config.require_content_review() else "pending"
        task.status = next_status
        task.error_message = None
        self.db.commit()
        self.db.refresh(task)
        return task

    def approve_task(self, task_id: int) -> PublishTask:
        task = self.get_task(task_id)
        if not task:
            raise ValueError("任务不存在")
        if task.status != "pending_review":
            raise ValueError("仅 pending_review 任务可审核通过")
        task.status = "pending"
        task.error_message = None
        self.db.commit()
        self.db.refresh(task)
        return task

    def reject_task(self, task_id: int, reason: str | None = None) -> PublishTask:
        task = self.get_task(task_id)
        if not task:
            raise ValueError("任务不存在")
        if task.status != "pending_review":
            raise ValueError("仅 pending_review 任务可驳回")
        task.status = "rejected"
        task.error_message = reason or "审核驳回"
        self.db.commit()
        self.db.refresh(task)
        return task

    def add_log(self, task_id: int, step: str, status: str, message: str | None = None) -> None:
        log = PublishTaskLog(task_id=task_id, step=step, status=status, message=message)
        self.db.add(log)
        self.db.commit()

    def list_logs(self, task_id: int) -> list[PublishTaskLog]:
        return (
            self.db.query(PublishTaskLog)
            .filter(PublishTaskLog.task_id == task_id)
            .order_by(PublishTaskLog.id.asc())
            .all()
        )

    async def execute_task(self, task_id: int, *, already_running: bool = False) -> PublishTask:
        task = self.get_task(task_id)
        if not task:
            raise ValueError("任务不存在")
        if not already_running:
            if task.status == "running":
                raise ValueError("任务正在执行中")
            if task.status not in {"pending"}:
                raise ValueError("仅 pending 状态任务可执行")
            task.status = "running"
            task.error_message = None
            self.db.commit()
        self.add_log(task_id, "start", "running", "开始执行发布任务")
        try:
            result = await self.worker.run(task)
            task.status = "success" if result.success else "failed"
            task.error_message = None if result.success else result.message
            self.add_log(task_id, "finish", "success" if result.success else "failed", result.message)
        except Exception as exc:
            task.status = "failed"
            task.error_message = str(exc)
            self.add_log(task_id, "finish", "failed", str(exc))
        self.db.commit()
        self.db.refresh(task)
        return task

    def execute_task_background(self, task_id: int) -> None:
        asyncio.create_task(self._execute_background(task_id))

    async def _execute_background(self, task_id: int) -> None:
        from app.database import SessionLocal

        db = SessionLocal()
        try:
            service = PublishService(db)
            await service.execute_task(task_id)
        finally:
            db.close()

    def reopen_to_draft(self, task_id: int) -> PublishTask:
        task = self.get_task(task_id)
        if not task:
            raise ValueError("任务不存在")
        if task.status != "rejected":
            raise ValueError("仅 rejected 任务可退回草稿")
        task.status = "draft"
        task.error_message = None
        self.db.commit()
        self.db.refresh(task)
        return task

    def retry_task(self, task_id: int) -> PublishTask:
        task = self.get_task(task_id)
        if not task:
            raise ValueError("任务不存在")
        if task.status != "failed":
            raise ValueError("仅 failed 任务可重试")
        task.status = "pending"
        task.error_message = None
        self.db.commit()
        self.db.refresh(task)
        return task

    def delete_task(self, task_id: int) -> None:
        task = self.get_task(task_id)
        if not task:
            raise ValueError("任务不存在")
        if task.status != "draft":
            raise ValueError("仅 draft 状态任务可删除")
        self.db.query(PublishTaskLog).filter(PublishTaskLog.task_id == task_id).delete()
        self.db.delete(task)
        self.db.commit()
