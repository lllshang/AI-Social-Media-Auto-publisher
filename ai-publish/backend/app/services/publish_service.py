import asyncio
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.adapters.base import PublishContext
from app.adapters.factory import get_adapter_factory
from app.config import get_settings
from app.models import Material, PublishTask, PublishTaskLog, ReviewLog
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
        bilibili_tid: int | None = None,
        status: str = "draft",
        user_id: int | None = None,
    ) -> PublishTask:
        account = self.account_service.get_account(account_id)
        if not account:
            raise ValueError("账号不存在")
        if platform == "bilibili":
            if content_type != "video":
                raise ValueError("B站仅支持视频发布")
            if bilibili_tid is None:
                bilibili_tid = self.system_config.get_int("bilibili_default_tid", 21)
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
            bilibili_tid=bilibili_tid,
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
        bilibili_tid: int | None = None,
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
        if bilibili_tid is not None:
            task.bilibili_tid = bilibili_tid

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
        task.retry_count = 0
        task.next_retry_at = None
        self.db.commit()
        self.db.refresh(task)
        return task

    def assert_can_execute(self, task: PublishTask) -> None:
        if task.status != "pending":
            raise ValueError("仅 pending 状态任务可执行")
        if self.system_config.require_content_review():
            approved = (
                self.db.query(ReviewLog.id)
                .filter(ReviewLog.task_id == task.id, ReviewLog.action == "approved")
                .first()
            )
            if not approved:
                raise ValueError("内容审核已开启，该任务须先通过审核方可执行")

    def approve_task(self, task_id: int, reviewer_id: int | None = None) -> PublishTask:
        task = self.get_task(task_id)
        if not task:
            raise ValueError("任务不存在")
        if task.status != "pending_review":
            raise ValueError("仅 pending_review 任务可审核通过")
        task.status = "pending"
        task.error_message = None
        self.db.add(
            ReviewLog(
                task_id=task.id,
                action="approved",
                reviewer_id=reviewer_id,
            )
        )
        self.db.commit()
        self.db.refresh(task)
        return task

    def reject_task(self, task_id: int, reason: str | None = None, reviewer_id: int | None = None) -> PublishTask:
        task = self.get_task(task_id)
        if not task:
            raise ValueError("任务不存在")
        if task.status != "pending_review":
            raise ValueError("仅 pending_review 任务可驳回")
        comment = reason or "审核驳回"
        task.status = "rejected"
        task.error_message = comment
        self.db.add(
            ReviewLog(
                task_id=task.id,
                action="rejected",
                comment=comment,
                reviewer_id=reviewer_id,
            )
        )
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
            self.assert_can_execute(task)
            task.status = "running"
            task.error_message = None
            self.db.commit()
        self.add_log(task_id, "start", "running", "开始执行发布任务")
        try:
            result = await self.worker.run(task)
            if result.success:
                task.status = "success"
                task.error_message = None
                task.retry_count = 0
                task.next_retry_at = None
                self.add_log(task_id, "finish", "success", result.message)
            else:
                task.status = "failed"
                task.error_message = result.message
                self.add_log(task_id, "finish", "failed", result.message)
                self._schedule_auto_retry_if_needed(task)
        except Exception as exc:
            task.status = "failed"
            task.error_message = str(exc)
            self.add_log(task_id, "finish", "failed", str(exc))
            self._schedule_auto_retry_if_needed(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def _schedule_auto_retry_if_needed(self, task: PublishTask) -> None:
        if not self.system_config.auto_retry_enabled():
            task.next_retry_at = None
            return
        max_retries = self.system_config.max_auto_retries()
        delay_minutes = self.system_config.retry_delay_minutes()
        task.retry_count = (task.retry_count or 0) + 1
        if task.retry_count <= max_retries:
            task.next_retry_at = datetime.utcnow() + timedelta(minutes=delay_minutes)
            message = (
                f"将于 {delay_minutes} 分钟后自动重试"
                f"（{task.retry_count}/{max_retries}）"
            )
            base = task.error_message or "发布失败"
            task.error_message = f"{base}；{message}"
            self.add_log(task.id, "auto_retry", "scheduled", message)
        else:
            task.next_retry_at = None
            base = task.error_message or "发布失败"
            task.error_message = f"{base}；已达自动重试上限（{max_retries}）"
            self.add_log(task.id, "auto_retry", "exhausted", task.error_message)

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
        task.next_retry_at = None
        self.db.commit()
        self.db.refresh(task)
        return task

    def claim_auto_retry_task(self) -> int | None:
        if not self.system_config.auto_retry_enabled():
            return None
        now = datetime.utcnow()
        task = (
            self.db.query(PublishTask)
            .filter(
                PublishTask.status == "failed",
                PublishTask.next_retry_at.isnot(None),
                PublishTask.next_retry_at <= now,
            )
            .order_by(PublishTask.next_retry_at.asc(), PublishTask.id.asc())
            .first()
        )
        if not task:
            return None
        if (task.retry_count or 0) > self.system_config.max_auto_retries():
            task.next_retry_at = None
            self.db.commit()
            return None
        task.status = "pending"
        task.next_retry_at = None
        task.error_message = None
        self.db.commit()
        self.add_log(task.id, "auto_retry", "pending", "自动重试已入队")
        return task.id

    def delete_task(self, task_id: int) -> None:
        task = self.get_task(task_id)
        if not task:
            raise ValueError("任务不存在")
        if task.status != "draft":
            raise ValueError("仅 draft 状态任务可删除")
        self.db.query(PublishTaskLog).filter(PublishTaskLog.task_id == task_id).delete()
        self.db.delete(task)
        self.db.commit()
