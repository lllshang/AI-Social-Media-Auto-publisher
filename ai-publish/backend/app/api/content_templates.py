from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_permission
from app.models import User
from app.schemas import ContentTemplateCreate, ContentTemplateResponse, ContentTemplateUpdate
from app.services.content_template_service import ContentTemplateService
from app.utils.permissions import PERM_TEMPLATES_READ, PERM_TEMPLATES_WRITE

router = APIRouter(prefix="/api/content-templates", tags=["content-templates"])


@router.get("", response_model=list[ContentTemplateResponse])
def list_templates(
    industry: str | None = Query(default=None),
    platform: str | None = Query(default=None),
    status: str | None = Query(default="active"),
    include_disabled: bool = Query(default=False),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PERM_TEMPLATES_READ)),
):
    service = ContentTemplateService(db)
    return service.list_templates(
        industry=industry,
        platform=platform,
        status=status,
        include_disabled=include_disabled,
    )


@router.get("/industries")
def list_industries(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PERM_TEMPLATES_READ)),
):
    service = ContentTemplateService(db)
    return {"items": service.list_industries()}


@router.get("/{template_id}", response_model=ContentTemplateResponse)
def get_template(
    template_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PERM_TEMPLATES_READ)),
):
    service = ContentTemplateService(db)
    row = service.get(template_id)
    if not row:
        raise HTTPException(status_code=404, detail="模板不存在")
    return row


@router.post("", response_model=ContentTemplateResponse)
def create_template(
    data: ContentTemplateCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PERM_TEMPLATES_WRITE)),
):
    service = ContentTemplateService(db)
    return service.create(**data.model_dump())


@router.put("/{template_id}", response_model=ContentTemplateResponse)
def update_template(
    template_id: int,
    data: ContentTemplateUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PERM_TEMPLATES_WRITE)),
):
    service = ContentTemplateService(db)
    try:
        return service.update(template_id, **data.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
