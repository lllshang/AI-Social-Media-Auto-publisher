"""内容创作 API 路由"""

from app.dependencies import get_current_user, require_permission
from app.database import get_db
from app.utils.permissions import PERM_PUBLISH_WRITE
from app.schemas import (
    CreativeSessionCreate,
    CreativeSessionListResponse,
    CreativeSessionResponse,
    CopyResponse,
    CopyUpdateRequest,
    GenerationRequest,
    GenerationTaskResponse,
    PolishRequest,
    PolishResponse,
)
from app.services.create_service import CreateService

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

router = APIRouter(tags=["content-creation"])


@router.post("/api/create/session", response_model=CreativeSessionResponse)
async def create_session(
    data: CreativeSessionCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission(PERM_PUBLISH_WRITE)),
):
    svc = CreateService(db)
    session = svc.create_session(current_user.id, data)
    return CreativeSessionResponse.model_validate(session)


@router.get("/api/create/sessions", response_model=CreativeSessionListResponse)
def list_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user=Depends(require_permission(PERM_PUBLISH_WRITE)),
):
    svc = CreateService(db)
    items, total = svc.get_sessions(current_user.id, page, page_size)
    return CreativeSessionListResponse(
        items=[CreativeSessionResponse.model_validate(it) for it in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/api/create/{session_id}", response_model=CreativeSessionResponse)
def get_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission(PERM_PUBLISH_WRITE)),
):
    svc = CreateService(db)
    session = svc.get_session(session_id, current_user.id)
    if not session:
        raise HTTPException(status_code=404, detail="创作会话不存在")
    return CreativeSessionResponse.model_validate(session)


@router.delete("/api/create/{session_id}")
def delete_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission(PERM_PUBLISH_WRITE)),
):
    svc = CreateService(db)
    if not svc.delete_session(session_id, current_user.id):
        raise HTTPException(status_code=404, detail="创作会话不存在")
    return {"ok": True}


@router.post("/api/create/{session_id}/generate-copy", response_model=CopyResponse)
async def generate_copy(
    session_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission(PERM_PUBLISH_WRITE)),
):
    svc = CreateService(db)
    try:
        return await svc.generate_copy(session_id, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/api/create/{session_id}/polish", response_model=PolishResponse)
async def polish_copy(
    session_id: int,
    data: PolishRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission(PERM_PUBLISH_WRITE)),
):
    svc = CreateService(db)
    try:
        return await svc.polish_copy(session_id, current_user.id, data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/api/create/{session_id}/copy", response_model=CopyResponse)
def get_copy(
    session_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission(PERM_PUBLISH_WRITE)),
):
    svc = CreateService(db)
    try:
        return svc.get_copy(session_id, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/api/create/{session_id}/copy", response_model=CopyResponse)
def update_copy(
    session_id: int,
    data: CopyUpdateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission(PERM_PUBLISH_WRITE)),
):
    svc = CreateService(db)
    try:
        return svc.update_copy(session_id, current_user.id, data.model_dump(exclude_none=True))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/api/create/{session_id}/generate", response_model=GenerationTaskResponse)
async def start_content_generation(
    session_id: int,
    data: GenerationRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission(PERM_PUBLISH_WRITE)),
):
    svc = CreateService(db)
    try:
        task = await svc.start_generation(session_id, current_user.id, data)
        return GenerationTaskResponse.model_validate(task)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/api/create/{session_id}/generations", response_model=list[GenerationTaskResponse])
def list_generations(
    session_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission(PERM_PUBLISH_WRITE)),
):
    svc = CreateService(db)
    try:
        tasks = svc.get_generations(session_id, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return [GenerationTaskResponse.model_validate(t) for t in tasks]


@router.get("/api/create/generations/{gen_id}", response_model=GenerationTaskResponse)
def get_generation_status(
    gen_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission(PERM_PUBLISH_WRITE)),
):
    svc = CreateService(db)
    task = svc.get_generation(gen_id, current_user.id)
    if not task:
        raise HTTPException(status_code=404, detail="生成任务不存在")
    return GenerationTaskResponse.model_validate(task)


@router.post("/api/create/{session_id}/complete")
def complete_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission(PERM_PUBLISH_WRITE)),
):
    svc = CreateService(db)
    try:
        materials = svc.complete_session(session_id, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"ok": True, "materials": materials}
