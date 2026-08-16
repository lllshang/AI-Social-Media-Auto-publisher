from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_any_permission
from app.models import Material, PublishTask, User
from app.schemas import (
    MaterialSummary,
    PublishTaskResponse,
    ReviewHistoryItem,
    ReviewHistoryListResponse,
    ReviewPendingListResponse,
)
from app.services.publish_service import PublishService
from app.services.review_service import ReviewService
from app.utils.permissions import PERM_REVIEW_WRITE, PERM_TASKS_READ

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


def _task_response(
    task: PublishTask,
    materials: list[Material] | None = None,
    db: Session | None = None,
) -> PublishTaskResponse:
    payload = PublishTaskResponse.model_validate(task)
    if materials is not None:
        payload.materials = [
            MaterialSummary(id=m.id, name=m.name, type=m.type, url=m.url) for m in materials
        ]
    if db is not None:
        from app.services.platform_account_service import PlatformAccountService

        account_svc = PlatformAccountService(db)
        account = account_svc.get_account(task.account_id)
        if account:
            payload.account_name = account.account_name
            payload.worker_name = account_svc.get_worker_name(account.worker_id)
    return payload


@router.get("/pending", response_model=ReviewPendingListResponse)
def list_pending_reviews(
    platform: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    created_from: datetime | None = Query(default=None),
    created_to: datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_any_permission(PERM_TASKS_READ, PERM_REVIEW_WRITE)),
):
    service = ReviewService(db)
    publish = PublishService(db)
    items, total = service.list_pending(
        platform=platform,
        keyword=keyword,
        created_from=created_from,
        created_to=created_to,
        page=page,
        page_size=page_size,
    )
    return ReviewPendingListResponse(
        items=[_task_response(task, publish.get_task_materials(task), db=db) for task in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/history", response_model=ReviewHistoryListResponse)
def list_review_history(
    platform: str | None = Query(default=None),
    action: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    created_from: datetime | None = Query(default=None),
    created_to: datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_any_permission(PERM_TASKS_READ, PERM_REVIEW_WRITE)),
):
    service = ReviewService(db)
    items, total = service.list_history(
        platform=platform,
        action=action,
        keyword=keyword,
        created_from=created_from,
        created_to=created_to,
        page=page,
        page_size=page_size,
    )
    return ReviewHistoryListResponse(
        items=[ReviewHistoryItem.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )
