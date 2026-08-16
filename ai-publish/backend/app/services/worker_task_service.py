from __future__ import annotations

from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import Material, PlatformAccount, PublishTask, PublishTaskLog, PublishWorker
from app.services.material_service import MaterialService
from app.services.platform_account_service import PlatformAccountService
from app.services.publish_service import PublishService
from app.services.publish_worker_service import PublishWorkerService
from app.services.system_config_service import SystemConfigService
from app.workers.redis_queue import task_queue


class WorkerTaskService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.worker_service = PublishWorkerService(db)
        self.account_service = PlatformAccountService(db)
        self.material_service = MaterialService(db)
        self.publish_service = PublishService(db)

    def claim_task(self, worker: PublishWorker, timeout_seconds: int = 30) -> dict | None:
        queue_key = self.worker_service.worker_queue_key(worker.id)
        task_id = task_queue.dequeue_worker_blocking(queue_key, timeout=timeout_seconds)
        if task_id is None:
            return None
        task = self.publish_service.get_task(task_id)
        if not task:
            task_queue.re_enqueue_worker(queue_key, task_id)
            return None
        account = self.account_service.get_account(task.account_id)
        if not account or account.worker_id != worker.id:
            task_queue.re_enqueue_worker(queue_key, task_id)
            return None
        if task.status not in {"pending", "dispatching", "running"}:
            return None
        limit_result = self.publish_service.rate_limit.evaluate(task, exclude_task_id=task.id)
        if not limit_result.allowed:
            self.publish_service.add_log(task.id, "rate_limit", "pending", limit_result.message)
            if task.status in {"running", "dispatching"}:
                task.status = "pending"
                self.db.commit()
            task_queue.enqueue_execute(task.id)
            return None
        if task.status != "running":
            task.status = "running"
            task.worker_id = worker.id
            task.error_message = None
            self.db.commit()
        self.publish_service.add_log(
            task.id,
            "worker_claim",
            "running",
            f"本机 Worker「{worker.name}」已认领任务",
        )
        return self.build_task_bundle(task, account)

    def build_task_bundle(self, task: PublishTask, account: PlatformAccount) -> dict:
        cookie_plain = self.account_service.load_cookie_plain(account)
        if not cookie_plain:
            raise ValueError("账号 Cookie 不存在，请先扫码登录")
        materials: list[dict] = []
        for material_id in task.material_ids or []:
            material = self.material_service.get(material_id)
            if not material:
                continue
            materials.append(
                {
                    "id": material.id,
                    "type": material.type,
                    "filename": Path(material.file_path).name,
                }
            )
        bilibili_tid = None
        if task.platform == "bilibili":
            config = SystemConfigService(self.db)
            bilibili_tid = task.bilibili_tid or config.get_int("bilibili_default_tid", 21)
        return {
            "task_id": task.id,
            "platform": task.platform,
            "account_id": account.id,
            "account_name": account.account_name,
            "title": task.title,
            "content": task.content or "",
            "tags": task.tags or [],
            "content_type": task.content_type,
            "cover_text": task.cover_text,
            "publish_time": task.publish_time.isoformat() if task.publish_time else None,
            "bilibili_tid": bilibili_tid,
            "cookie_plain": cookie_plain,
            "publish_proxy": account.publish_proxy,
            "materials": materials,
        }

    def append_log(self, task_id: int, step: str, status: str, message: str | None = None) -> None:
        log = PublishTaskLog(task_id=task_id, step=step, status=status, message=message)
        self.db.add(log)
        self.db.commit()

    def finish_task(self, task_id: int, *, success: bool, message: str) -> PublishTask:
        task = self.publish_service.get_task(task_id)
        if not task:
            raise ValueError("任务不存在")
        if success:
            task.status = "success"
            task.error_message = None
            task.retry_count = 0
            task.next_retry_at = None
            self.append_log(task_id, "finish", "success", message)
        else:
            task.status = "failed"
            task.error_message = message
            self.append_log(task_id, "finish", "failed", message)
            self.publish_service._schedule_auto_retry_if_needed(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def get_material_file(self, worker: PublishWorker, material_id: int) -> tuple[Material, Path]:
        material = self.material_service.get(material_id)
        if not material:
            raise ValueError("素材不存在")
        path = Path(material.file_path)
        if not path.exists():
            raise ValueError("素材文件不存在")
        return material, path
