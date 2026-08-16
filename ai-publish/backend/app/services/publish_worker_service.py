from __future__ import annotations

import hashlib
import re
import secrets
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import PlatformAccount, PublishTask, PublishWorker

WORKER_ONLINE_SECONDS = 90


def _slugify(name: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9_-]+", "-", name.strip().lower()).strip("-")
    return value or "worker"


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class PublishWorkerService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_workers(self) -> list[PublishWorker]:
        return self.db.query(PublishWorker).order_by(PublishWorker.id.asc()).all()

    def get_worker(self, worker_id: int) -> PublishWorker | None:
        return self.db.query(PublishWorker).filter(PublishWorker.id == worker_id).first()

    def get_worker_by_token(self, token: str) -> PublishWorker | None:
        if not token:
            return None
        token_hash = _hash_token(token)
        return (
            self.db.query(PublishWorker)
            .filter(PublishWorker.token_hash == token_hash, PublishWorker.status == "active")
            .first()
        )

    def is_online(self, worker: PublishWorker, *, now: datetime | None = None) -> bool:
        if not worker.last_heartbeat_at:
            return False
        current = now or datetime.utcnow()
        return worker.last_heartbeat_at >= current - timedelta(seconds=WORKER_ONLINE_SECONDS)

    def create_worker(self, name: str) -> tuple[PublishWorker, str]:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Worker 名称不能为空")
        base_key = _slugify(clean_name)
        worker_key = base_key
        suffix = 1
        while self.db.query(PublishWorker).filter(PublishWorker.worker_key == worker_key).first():
            worker_key = f"{base_key}-{suffix}"
            suffix += 1
        token = secrets.token_urlsafe(32)
        worker = PublishWorker(
            name=clean_name,
            worker_key=worker_key,
            token_hash=_hash_token(token),
            status="active",
        )
        self.db.add(worker)
        self.db.commit()
        self.db.refresh(worker)
        return worker, token

    def rotate_token(self, worker_id: int) -> tuple[PublishWorker, str]:
        worker = self.get_worker(worker_id)
        if not worker:
            raise ValueError("Worker 不存在")
        token = secrets.token_urlsafe(32)
        worker.token_hash = _hash_token(token)
        worker.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(worker)
        return worker, token

    def delete_worker(self, worker_id: int) -> None:
        worker = self.get_worker(worker_id)
        if not worker:
            raise ValueError("Worker 不存在")
        bound_accounts = (
            self.db.query(PlatformAccount).filter(PlatformAccount.worker_id == worker_id).count()
        )
        if bound_accounts:
            raise ValueError(f"仍有 {bound_accounts} 个账号绑定此 Worker，请先解绑")
        self.db.delete(worker)
        self.db.commit()

    def heartbeat(self, worker: PublishWorker, hostname: str | None = None) -> PublishWorker:
        worker.last_heartbeat_at = datetime.utcnow()
        if hostname:
            worker.hostname = hostname.strip()[:128] or worker.hostname
        worker.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(worker)
        return worker

    def resolve_worker_for_task(self, task_id: int) -> int | None:
        task = self.db.query(PublishTask).filter(PublishTask.id == task_id).first()
        if not task:
            return None
        account = self.db.query(PlatformAccount).filter(PlatformAccount.id == task.account_id).first()
        if not account or not account.worker_id:
            return None
        worker = self.get_worker(account.worker_id)
        if not worker or worker.status != "active":
            return None
        return worker.id

    def worker_queue_key(self, worker_id: int) -> str:
        worker = self.get_worker(worker_id)
        if not worker:
            raise ValueError("Worker 不存在")
        return f"ai-publish:queue:worker:{worker.worker_key}"
