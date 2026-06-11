from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_worker, require_permission
from app.models import PublishWorker, User
from app.schemas import (
    PublishWorkerClaimRequest,
    PublishWorkerClaimResponse,
    PublishWorkerCreate,
    PublishWorkerCreateResponse,
    PublishWorkerHeartbeatRequest,
    PublishWorkerResponse,
    PublishWorkerRotateTokenResponse,
    WorkerTaskFinishRequest,
    WorkerTaskLogRequest,
)
from app.services.log_service import LogService
from app.services.publish_worker_service import PublishWorkerService
from app.services.worker_task_service import WorkerTaskService
from app.utils.permissions import PERM_SETTINGS_WRITE

router = APIRouter(prefix="/api/publish-workers", tags=["publish-workers"])


def _worker_response(worker: PublishWorker, service: PublishWorkerService) -> PublishWorkerResponse:
    return PublishWorkerResponse(
        id=worker.id,
        name=worker.name,
        worker_key=worker.worker_key,
        hostname=worker.hostname,
        online=service.is_online(worker),
        status=worker.status,
        last_heartbeat_at=worker.last_heartbeat_at,
        created_at=worker.created_at,
    )


@router.get("", response_model=list[PublishWorkerResponse])
def list_workers(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PERM_SETTINGS_WRITE)),
):
    service = PublishWorkerService(db)
    return [_worker_response(worker, service) for worker in service.list_workers()]


@router.post("", response_model=PublishWorkerCreateResponse)
def create_worker(
    data: PublishWorkerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PERM_SETTINGS_WRITE)),
):
    service = PublishWorkerService(db)
    try:
        worker, token = service.create_worker(data.name)
        LogService(db).add_operation(
            "publish_worker.create",
            current_user.id,
            "publish_worker",
            worker.id,
        )
        response = _worker_response(worker, service)
        return PublishWorkerCreateResponse(**response.model_dump(), token=token)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{worker_id}/rotate-token", response_model=PublishWorkerRotateTokenResponse)
def rotate_worker_token(
    worker_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PERM_SETTINGS_WRITE)),
):
    service = PublishWorkerService(db)
    try:
        worker, token = service.rotate_token(worker_id)
        LogService(db).add_operation(
            "publish_worker.rotate_token",
            current_user.id,
            "publish_worker",
            worker.id,
        )
        response = _worker_response(worker, service)
        return PublishWorkerRotateTokenResponse(**response.model_dump(), token=token)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{worker_id}")
def delete_worker(
    worker_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PERM_SETTINGS_WRITE)),
):
    service = PublishWorkerService(db)
    try:
        service.delete_worker(worker_id)
        LogService(db).add_operation(
            "publish_worker.delete",
            current_user.id,
            "publish_worker",
            worker_id,
        )
        return {"success": True}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/heartbeat", response_model=PublishWorkerResponse)
def worker_heartbeat(
    data: PublishWorkerHeartbeatRequest,
    db: Session = Depends(get_db),
    worker: PublishWorker = Depends(get_current_worker),
):
    service = PublishWorkerService(db)
    updated = service.heartbeat(worker, data.hostname)
    return _worker_response(updated, service)


@router.post("/claim", response_model=PublishWorkerClaimResponse)
def worker_claim(
    data: PublishWorkerClaimRequest,
    db: Session = Depends(get_db),
    worker: PublishWorker = Depends(get_current_worker),
):
    service = PublishWorkerService(db)
    service.heartbeat(worker, data.hostname)
    task_service = WorkerTaskService(db)
    try:
        bundle = task_service.claim_task(worker, timeout_seconds=data.timeout_seconds)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PublishWorkerClaimResponse(task=bundle)


@router.get("/materials/{material_id}/download")
def worker_download_material(
    material_id: int,
    db: Session = Depends(get_db),
    worker: PublishWorker = Depends(get_current_worker),
):
    task_service = WorkerTaskService(db)
    try:
        material, path = task_service.get_material_file(worker, material_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(path, filename=Path(material.file_path).name)


@router.post("/tasks/{task_id}/logs")
def worker_append_log(
    task_id: int,
    data: WorkerTaskLogRequest,
    db: Session = Depends(get_db),
    worker: PublishWorker = Depends(get_current_worker),
):
    task_service = WorkerTaskService(db)
    task_service.append_log(task_id, data.step, data.status, data.message)
    return {"success": True}


@router.post("/tasks/{task_id}/finish")
def worker_finish_task(
    task_id: int,
    data: WorkerTaskFinishRequest,
    db: Session = Depends(get_db),
    worker: PublishWorker = Depends(get_current_worker),
):
    task_service = WorkerTaskService(db)
    try:
        task = task_service.finish_task(task_id, success=data.success, message=data.message)
        return {"success": True, "status": task.status}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
