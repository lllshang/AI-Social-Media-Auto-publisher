from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_permission
from app.models import User
from app.utils.permissions import PERM_MODELS_READ, PERM_MODELS_WRITE
from app.services.ai_model_service import AiModelService

router = APIRouter(prefix="/api/ai/models", tags=["ai-models"])


class AiModelSelectRequest(BaseModel):
    mode: str | None = Field(default=None, description="auto 或 manual")
    text_provider: str | None = None
    text_model: str | None = None
    image_provider: str | None = None
    image_model: str | None = None
    video_provider: str | None = None
    video_model: str | None = None


class AiProviderConfigRequest(BaseModel):
    provider: str
    api_key: str | None = None
    secret_key: str | None = None
    sub_app_id: str | None = None
    base_url: str | None = None
    clear_key: bool = False


class AiCustomProviderRequest(BaseModel):
    label: str
    base_url: str
    kind: str = "text"
    text_models: list[str] = Field(default_factory=list)
    image_models: list[str] = Field(default_factory=list)
    api_key: str | None = None


@router.get("/providers")
def list_providers(_: User = Depends(require_permission(PERM_MODELS_READ))):
    service = AiModelService()
    return {"items": service.list_provider_configs()}


@router.post("/providers/custom")
def add_custom_provider(data: AiCustomProviderRequest, _: User = Depends(require_permission(PERM_MODELS_WRITE))):
    service = AiModelService()
    try:
        item = service.add_custom_provider(
            label=data.label,
            base_url=data.base_url,
            kind=data.kind,
            text_models=data.text_models,
            image_models=data.image_models,
            api_key=data.api_key,
        )
        return item
    except ValueError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/providers/custom/{provider}")
def delete_custom_provider(provider: str, _: User = Depends(require_permission(PERM_MODELS_WRITE))):
    service = AiModelService()
    try:
        service.delete_custom_provider(provider)
        return {"ok": True}
    except ValueError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/providers/config")
def save_provider_config(data: AiProviderConfigRequest, _: User = Depends(require_permission(PERM_MODELS_WRITE))):
    service = AiModelService()
    try:
        item = service.save_provider_config(
            data.provider,
            api_key=data.api_key,
            secret_key=data.secret_key,
            sub_app_id=data.sub_app_id,
            base_url=data.base_url,
            clear_key=data.clear_key,
        )
        return item
    except ValueError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("")
async def list_models(_: User = Depends(require_permission(PERM_MODELS_READ))):
    service = AiModelService()
    result = await service.detect_all()
    return result.to_dict()


@router.post("/detect")
async def detect_models(_: User = Depends(require_permission(PERM_MODELS_WRITE))):
    service = AiModelService()
    runtime = service.load_runtime()
    runtime.mode = "auto"
    service.save_runtime(runtime)
    result = await service.detect_all()
    return result.to_dict()


@router.get("/current")
async def current_models(_: User = Depends(require_permission(PERM_MODELS_READ))):
    service = AiModelService()
    runtime = service.load_runtime()
    text_provider, text_model = service._resolve_text_target()
    image_provider, image_model = service._resolve_image_target()
    return {
        "runtime": runtime.to_dict(),
        "text": {"provider": text_provider, "model": text_model},
        "image": {"provider": image_provider, "model": image_model},
    }


@router.post("/select")
async def select_models(data: AiModelSelectRequest, _: User = Depends(require_permission(PERM_MODELS_WRITE))):
    service = AiModelService()
    runtime = service.set_selection(
        mode=data.mode or "manual",
        text_provider=data.text_provider,
        text_model=data.text_model,
        image_provider=data.image_provider,
        image_model=data.image_model,
        video_provider=data.video_provider,
        video_model=data.video_model,
    )
    result = await service.detect_all()
    result.runtime = runtime.to_dict()
    return result.to_dict()
