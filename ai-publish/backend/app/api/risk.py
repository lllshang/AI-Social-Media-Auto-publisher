from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_permission
from app.models import User
from app.schemas import (
    SensitiveWordBatchCreate,
    SensitiveWordCreate,
    SensitiveWordResponse,
)
from app.services.sensitive_word_service import SensitiveWordService
from app.utils.permissions import PERM_SETTINGS_WRITE

router = APIRouter(prefix="/api/risk", tags=["risk"])


@router.get("/sensitive-words", response_model=list[SensitiveWordResponse])
def list_sensitive_words(
    include_disabled: bool = False,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PERM_SETTINGS_WRITE)),
):
    service = SensitiveWordService(db)
    return service.list_words(include_disabled=include_disabled)


@router.post("/sensitive-words", response_model=SensitiveWordResponse)
def create_sensitive_word(
    data: SensitiveWordCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PERM_SETTINGS_WRITE)),
):
    service = SensitiveWordService(db)
    try:
        return service.add_word(data.word, remark=data.remark)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/sensitive-words/batch")
def batch_import_sensitive_words(
    data: SensitiveWordBatchCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PERM_SETTINGS_WRITE)),
):
    service = SensitiveWordService(db)
    added = service.batch_import(data.words)
    return {"added": added}


@router.delete("/sensitive-words/{word_id}")
def delete_sensitive_word(
    word_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PERM_SETTINGS_WRITE)),
):
    service = SensitiveWordService(db)
    try:
        service.delete_word(word_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True}
