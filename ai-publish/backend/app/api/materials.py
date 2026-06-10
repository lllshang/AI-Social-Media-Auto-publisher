from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas import ImageGenerateRequest, MaterialResponse, PromptBuildRequest, PromptBuildResponse, TextGenerateRequest
from app.utils.prompt_templates import build_prompt
from app.services.material_service import AiContentService, MaterialService

router = APIRouter(tags=["materials", "ai"])


@router.post("/api/materials/upload", response_model=MaterialResponse)
async def upload_material(
    file: UploadFile = File(...),
    name: str | None = Form(default=None),
    category: str | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = MaterialService(db)
    return await service.upload(file, current_user.id, name=name, category=category)


@router.get("/api/materials/categories")
def list_categories(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    service = MaterialService(db)
    return {"items": service.list_categories()}


@router.get("/api/materials", response_model=list[MaterialResponse])
def list_materials(
    material_type: str | None = Query(default=None),
    category: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    service = MaterialService(db)
    return service.list_materials(material_type=material_type, category=category, keyword=keyword)


@router.get("/api/materials/{material_id}", response_model=MaterialResponse)
def get_material(
    material_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    service = MaterialService(db)
    material = service.get(material_id)
    if not material:
        raise HTTPException(status_code=404, detail="素材不存在")
    return material


@router.delete("/api/materials/{material_id}")
def delete_material(
    material_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    service = MaterialService(db)
    try:
        service.delete_material(material_id)
        return {"success": True}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/api/ai/prompt/build", response_model=PromptBuildResponse)
def build_ai_prompt(
    data: PromptBuildRequest,
    _: User = Depends(get_current_user),
):
    if data.kind not in {"text", "image"}:
        raise HTTPException(status_code=400, detail="kind 仅支持 text 或 image")
    template_name, prompt = build_prompt(
        data.kind,
        data.platform,
        data.topic,
        content_type=data.content_type,
        ratio=data.ratio,
        style=data.style,
        cover_text=data.cover_text,
    )
    return PromptBuildResponse(
        kind=data.kind,
        platform=data.platform,
        template_name=template_name,
        prompt=prompt,
    )


@router.post("/api/ai/text/generate")
async def generate_text(
    data: TextGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.adapters.ai_text.openai_compatible import AiProviderError

    service = AiContentService(db)
    try:
        return await service.generate_text(
            data.topic,
            data.platform,
            current_user.id,
            data.content_type,
        )
    except AiProviderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"文案生成失败: {exc}") from exc


@router.post("/api/ai/image/generate")
async def generate_image(
    data: ImageGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = AiContentService(db)
    try:
        return await service.generate_image(
            data.topic,
            data.platform,
            data.ratio,
            data.count,
            data.cover_text,
            current_user.id,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"文生图失败: {exc}") from exc
