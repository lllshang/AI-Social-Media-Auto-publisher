from datetime import datetime

from sqlalchemy.orm import Session

from app.models import PublishTask, ReviewLog, User
from app.services.publish_service import PublishService


class ReviewService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.publish_service = PublishService(db)

    def list_pending(
        self,
        *,
        platform: str | None = None,
        keyword: str | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[PublishTask], int]:
        query = self.db.query(PublishTask).filter(PublishTask.status == "pending_review")
        if platform:
            query = query.filter(PublishTask.platform == platform)
        if keyword:
            query = query.filter(PublishTask.title.like(f"%{keyword}%"))
        if created_from:
            query = query.filter(PublishTask.created_at >= created_from)
        if created_to:
            query = query.filter(PublishTask.created_at <= created_to)
        total = query.count()
        items = (
            query.order_by(PublishTask.id.desc())
            .offset(max(page - 1, 0) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    def list_history(
        self,
        *,
        platform: str | None = None,
        action: str | None = None,
        keyword: str | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict], int]:
        query = (
            self.db.query(ReviewLog, PublishTask, User)
            .join(PublishTask, PublishTask.id == ReviewLog.task_id)
            .outerjoin(User, User.id == ReviewLog.reviewer_id)
        )
        if platform:
            query = query.filter(PublishTask.platform == platform)
        if action:
            query = query.filter(ReviewLog.action == action)
        if keyword:
            query = query.filter(PublishTask.title.like(f"%{keyword}%"))
        if created_from:
            query = query.filter(ReviewLog.created_at >= created_from)
        if created_to:
            query = query.filter(ReviewLog.created_at <= created_to)
        total = query.count()
        rows = (
            query.order_by(ReviewLog.id.desc())
            .offset(max(page - 1, 0) * page_size)
            .limit(page_size)
            .all()
        )
        items = [
            {
                "id": log.id,
                "task_id": log.task_id,
                "task_title": task.title,
                "platform": task.platform,
                "action": log.action,
                "comment": log.comment,
                "reviewer_id": log.reviewer_id,
                "reviewer_name": reviewer.username if reviewer else None,
                "created_at": log.created_at,
            }
            for log, task, reviewer in rows
        ]
        return items, total

    def add_log(self, task_id: int, action: str, reviewer_id: int | None, comment: str | None = None) -> ReviewLog:
        log = ReviewLog(
            task_id=task_id,
            action=action,
            comment=comment,
            reviewer_id=reviewer_id,
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log
