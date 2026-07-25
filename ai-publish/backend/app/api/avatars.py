"""数字人 / 仿真人 Avatar API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pathlib import Path
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_permission
from app.models import User
from app.schemas import AvatarCreate, AvatarResponse, AvatarUpdate
from app.services.avatar_service import AvatarService
from app.utils.permissions import PERM_AVATARS_READ, PERM_AVATARS_WRITE

router = APIRouter(tags=["avatars"])


@router.get("/api/avatars", response_model=list[AvatarResponse])
def list_avatars(
    type: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PERM_AVATARS_READ)),
):
    service = AvatarService(db)
    avatars = service.list_avatars(type=type)
    return [service.to_response(a) for a in avatars]


@router.get("/api/avatars/{avatar_id}", response_model=AvatarResponse)
def get_avatar(
    avatar_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PERM_AVATARS_READ)),
):
    service = AvatarService(db)
    avatar = service.get(avatar_id)
    if not avatar:
        raise HTTPException(status_code=404, detail="Avatar 不存在")
    return service.to_response(avatar)


@router.post("/api/avatars", response_model=AvatarResponse)
def create_avatar(
    data: AvatarCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PERM_AVATARS_WRITE)),
):
    service = AvatarService(db)
    avatar = service.create(data, user_id=current_user.id)
    return service.to_response(avatar)


@router.put("/api/avatars/{avatar_id}", response_model=AvatarResponse)
def update_avatar(
    avatar_id: int,
    data: AvatarUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PERM_AVATARS_WRITE)),
):
    service = AvatarService(db)
    try:
        avatar = service.update(avatar_id, data)
        return service.to_response(avatar)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/api/avatars/{avatar_id}")
def delete_avatar(
    avatar_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PERM_AVATARS_WRITE)),
):
    service = AvatarService(db)
    try:
        service.delete(avatar_id)
        return {"success": True}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/api/avatars/{avatar_id}/upload-thumbnail")
async def upload_avatar_thumbnail(
    avatar_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PERM_AVATARS_WRITE)),
):
    from app.adapters.factory import get_adapter_factory

    service = AvatarService(db)
    avatar = service.get(avatar_id)
    if not avatar:
        raise HTTPException(status_code=404, detail="Avatar 不存在")
    content = await file.read()
    factory = get_adapter_factory()
    storage = factory.get_storage_adapter()
    suffix = Path(file.filename or "image.jpg").suffix or ".jpg"
    file_path = storage.save_bytes(content, suffix=suffix)
    url = storage.get_url(file_path)
    avatar.thumbnail = file_path
    db.commit()
    return {"thumbnail_url": url}
