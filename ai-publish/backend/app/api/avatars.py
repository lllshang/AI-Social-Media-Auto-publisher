"""数字人 / 仿真人 Avatar API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pathlib import Path
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_permission
from app.models import User
from app.schemas import AvatarCreate, AvatarResponse, AvatarUpdate
from app.adapters.base import ImageGenerateInput
from app.services.avatar_service import AvatarService
from app.utils.permissions import PERM_AVATARS_READ, PERM_AVATARS_WRITE

router = APIRouter(tags=["avatars"])


class GenerateBackgroundRequest(BaseModel):
    """为已存在数字人生成背景参考图(腾讯云 VOD AIGC 图生图)。

    - background_prompt: 留空时使用 avatar 已有的 background_prompt
    - count: 一次性生成几张供用户挑选(默认 1)
    - ratio: 画幅比例(默认 3:4)
    - store: 是否生成后自动把第一张候选图写入 avatar.background_image_url(默认 True),
      该字段用于数字人视频生成时作为带背景驱动图;前端仍可单独"应用为预览图"
    """

    background_prompt: str | None = None
    count: int = 1
    ratio: str = "3:4"
    store: bool = True


class GenerateBackgroundResponse(BaseModel):
    image_urls: list[str]
    provider: str
    background_prompt: str
    background_image_url: str | None = None


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


@router.post(
    "/api/avatars/{avatar_id}/generate-background",
    response_model=GenerateBackgroundResponse,
)
async def generate_avatar_background(
    avatar_id: int,
    payload: GenerateBackgroundRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PERM_AVATARS_WRITE)),
):
    """调用腾讯云 VOD AIGC 图生图,基于 avatar 的参考图 + 背景描述生成 2 张候选图。

    - 返回生成的 image_urls 供预览挑选;
    - 默认把第一张候选图写入 avatar.background_image_url(虚拟路径),
      用于数字人视频生成时作为「带背景」驱动图;不覆盖原 thumbnail。
    - 前端若想把某张候选图设为预览图,可单独调用 PUT /api/avatars/{id}(带 thumbnail)。
    """
    from app.adapters.factory import get_adapter_factory

    service = AvatarService(db)
    avatar = service.get(avatar_id)
    if not avatar:
        raise HTTPException(status_code=404, detail="Avatar 不存在")
    if not avatar.reference_image_url:
        raise HTTPException(
            status_code=400,
            detail="该数字人尚未上传参考图(reference_image_url),无法生成背景图",
        )

    prompt = (payload.background_prompt or avatar.background_prompt or "").strip()
    if not prompt:
        raise HTTPException(
            status_code=400,
            detail="请提供背景描述 background_prompt(可在请求中或 avatar.background_prompt)",
        )

    # 参考图压缩预处理 + 图生图均在 adapter 内部完成(tencent_vod._prepare_reference_image)
    # avatar.reference_image_url 通常是 /static/... 容器内相对路径，
    # 会被 tencent_vod.generate_image 自动 _absolutize_url 转为公网 URL
    adapter = get_adapter_factory().get_ai_video_adapter()
    inp = ImageGenerateInput(
        topic="数字人背景生成",
        ratio=payload.ratio,
        count=payload.count,
        reference_image_url=avatar.reference_image_url,
        background_prompt=prompt,
    )
    result = await adapter.generate_image(inp)

    stored_bg = None
    if payload.store and result.image_paths:
        # 第一张候选图作为带背景参考图。
        # adapter 返回的 image_paths 是容器内绝对路径(如 /data/materials/xxx.jpg)，
        # 这里过 storage.get_url 归一化为 /static/materials/xxx.jpg，
        # 这样 FastAPI 的 /static/materials 路由可访问、腾讯云也能公网拉取。
        from app.adapters.factory import get_adapter_factory as _factory
        storage = _factory().get_storage_adapter()
        avatar.background_image_url = storage.get_url(result.image_paths[0])
        db.commit()
        stored_bg = avatar.background_image_url

    # response.image_urls 必须是前端可直接渲染的 URL。
    # adapter 返回的是容器内路径（如 /data/materials/xxx.jpg），
    # 这里统一过 storage.get_url 归一化为 /static/materials/xxx.jpg。
    public_urls = (
        [storage.get_url(p) for p in result.image_paths]
        if result.image_paths
        else []
    )

    return GenerateBackgroundResponse(
        image_urls=public_urls,
        provider=result.provider,
        background_prompt=prompt,
        background_image_url=stored_bg or avatar.background_image_url,
    )
