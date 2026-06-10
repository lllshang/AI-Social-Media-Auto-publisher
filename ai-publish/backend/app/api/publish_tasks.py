from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_permission
from app.utils.permissions import (
    PERM_TASKS_EXECUTE,
    PERM_TASKS_READ,
    PERM_TASKS_WRITE,
)
from app.models import Material, PublishTask, User
from app.schemas import (
    MaterialSummary,
    PublishTaskCreate,
    PublishTaskLogResponse,
    PublishTaskResponse,
    PublishTaskUpdate,
)
from app.services.publish_service import PublishService
from app.workers.redis_queue import task_queue

router = APIRouter(prefix="/api/publish-tasks", tags=["publish-tasks"])


class RejectTaskRequest(BaseModel):
    reason: str | None = None


def _task_response(task: PublishTask, materials: list[Material] | None = None) -> PublishTaskResponse:
    payload = PublishTaskResponse.model_validate(task)
    if materials is not None:
        payload.materials = [
            MaterialSummary(id=m.id, name=m.name, type=m.type, url=m.url) for m in materials
        ]
    return payload


@router.get("", response_model=list[PublishTaskResponse])
def list_tasks(
    status: str | None = Query(default=None),
    platform: str | None = Query(default=None),
    keyword: str | None = Query(default=None, description="标题关键字"),
    created_from: datetime | None = Query(default=None),
    created_to: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PERM_TASKS_READ)),
):
    service = PublishService(db)
    return [_task_response(task) for task in service.list_tasks(
        status=status,
        platform=platform,
        keyword=keyword,
        created_from=created_from,
        created_to=created_to,
    )]


@router.post("", response_model=PublishTaskResponse)
def create_task(
    data: PublishTaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PERM_TASKS_WRITE)),
):
    service = PublishService(db)
    try:
        if data.submit:
            initial_status = "pending_review" if service.system_config.require_content_review() else "pending"
        else:
            initial_status = "draft"
        task = service.create_task(
            title=data.title,
            content=data.content,
            comment_guide=data.comment_guide,
            topic=data.topic,
            cover_text=data.cover_text,
            wizard_step=data.wizard_step,
            tags=data.tags,
            platform=data.platform,
            account_id=data.account_id,
            material_ids=data.material_ids,
            content_type=data.content_type,
            publish_time=data.publish_time,
            status=initial_status,
            user_id=current_user.id,
        )
        return _task_response(task, service.get_task_materials(task))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{task_id}", response_model=PublishTaskResponse)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    service = PublishService(db)
    task = service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return _task_response(task, service.get_task_materials(task))


@router.put("/{task_id}", response_model=PublishTaskResponse)
def update_task(
    task_id: int,
    data: PublishTaskUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    service = PublishService(db)
    try:
        task = service.update_task(
            task_id,
            title=data.title,
            content=data.content,
            comment_guide=data.comment_guide,
            topic=data.topic,
            cover_text=data.cover_text,
            wizard_step=data.wizard_step,
            tags=data.tags,
            account_id=data.account_id,
            material_ids=data.material_ids,
            publish_time=data.publish_time,
        )
        return _task_response(task, service.get_task_materials(task))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{task_id}/submit", response_model=PublishTaskResponse)
def submit_task(
    task_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    service = PublishService(db)
    try:
        task = service.submit_task(task_id)
        return _task_response(task, service.get_task_materials(task))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{task_id}/approve", response_model=PublishTaskResponse)
def approve_task(
    task_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    service = PublishService(db)
    try:
        task = service.approve_task(task_id)
        return _task_response(task, service.get_task_materials(task))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{task_id}/reject", response_model=PublishTaskResponse)
def reject_task(
    task_id: int,
    data: RejectTaskRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    service = PublishService(db)
    try:
        task = service.reject_task(task_id, data.reason)
        return _task_response(task, service.get_task_materials(task))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{task_id}/execute", response_model=PublishTaskResponse)
def execute_task(
    task_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PERM_TASKS_EXECUTE)),
):
    service = PublishService(db)
    task = service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.status == "running":
        raise HTTPException(status_code=409, detail="任务正在执行中")
    if task.status != "pending":
        raise HTTPException(status_code=400, detail="仅 pending 状态任务可执行")
    task.status = "running"
    db.commit()
    db.refresh(task)
    task_queue.enqueue_execute(task_id)
    return _task_response(task, service.get_task_materials(task))


@router.post("/{task_id}/reopen", response_model=PublishTaskResponse)
def reopen_task(
    task_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    service = PublishService(db)
    try:
        task = service.reopen_to_draft(task_id)
        return _task_response(task, service.get_task_materials(task))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{task_id}/retry", response_model=PublishTaskResponse)
def retry_task(
    task_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    service = PublishService(db)
    try:
        task = service.retry_task(task_id)
        return _task_response(task, service.get_task_materials(task))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{task_id}/logs", response_model=list[PublishTaskLogResponse])
def list_logs(
    task_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    service = PublishService(db)
    if not service.get_task(task_id):
        raise HTTPException(status_code=404, detail="任务不存在")
    return service.list_logs(task_id)


@router.delete("/{task_id}")
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    service = PublishService(db)
    try:
        service.delete_task(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True}
