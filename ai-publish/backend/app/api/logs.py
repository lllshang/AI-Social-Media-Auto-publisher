from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_permission
from app.utils.permissions import PERM_LOGS_READ
from app.models import User
from app.schemas import AiGenerationRecordResponse, OperationLogResponse
from app.services.log_service import LogService

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("/ai-generations", response_model=list[AiGenerationRecordResponse])
def list_ai_generations(
    record_type: str | None = Query(default=None, alias="type"),
    provider: str | None = Query(default=None),
    created_from: datetime | None = Query(default=None),
    created_to: datetime | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PERM_LOGS_READ)),
):
    service = LogService(db)
    return service.list_ai_records(
        record_type=record_type,
        provider=provider,
        created_from=created_from,
        created_to=created_to,
        limit=limit,
    )


@router.get("/operations", response_model=list[OperationLogResponse])
def list_operations(
    action: str | None = Query(default=None),
    target_type: str | None = Query(default=None),
    created_from: datetime | None = Query(default=None),
    created_to: datetime | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PERM_LOGS_READ)),
):
    service = LogService(db)
    return service.list_operation_logs(
        action=action,
        target_type=target_type,
        created_from=created_from,
        created_to=created_to,
        limit=limit,
    )
