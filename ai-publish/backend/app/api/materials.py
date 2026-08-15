from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_any_permission, require_permission
from app.models import User
from app.utils.permissions import PERM_MATERIALS_READ, PERM_MATERIALS_WRITE, PERM_PUBLISH_WRITE
from app.schemas import (
    ImageGenerateRequest,
    MaterialResponse,
    PromptBuildRequest,
    PromptBuildResponse,
    TextGenerateRequest,
    TextMaterialCreate,
    TextPolishRequest,
    VideoGenerateRequest,
)
from app.utils.prompt_templates import build_prompt_details
from app.services.material_service import AiContentService, MaterialService

router = APIRouter(tags=["materials", "ai"])


@router.post("/api/materials/upload", response_model=MaterialResponse)
async def upload_material(
    file: UploadFile = File(...),
    name: str | None = Form(default=None),
    category: str | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PERM_MATERIALS_WRITE)),
):
    service = MaterialService(db)
    material = await service.upload(file, current_user.id, name=name, category=category)
    return service.to_response(material)


@router.get("/api/materials/categories")
def list_categories(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PERM_MATERIALS_READ)),
):
    service = MaterialService(db)
    return {"items": service.list_categories()}


@router.get("/api/materials", response_model=list[MaterialResponse])
def list_materials(
    material_type: str | None = Query(default=None),
    category: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PERM_MATERIALS_READ)),
):
    service = MaterialService(db)
    items = service.list_materials(material_type=material_type, category=category, keyword=keyword)
    return [service.to_response(item) for item in items]


@router.get("/api/materials/{material_id}", response_model=MaterialResponse)
def get_material(
    material_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PERM_MATERIALS_READ)),
):
    service = MaterialService(db)
    material = service.get(material_id)
    if not material:
        raise HTTPException(status_code=404, detail="素材不存在")
    return service.to_response(material, include_text_body=True)


@router.post("/api/materials/text", response_model=MaterialResponse)
def save_text_material(
    data: TextMaterialCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PERM_MATERIALS_WRITE)),
):
    service = MaterialService(db)
    material = service.save_text_draft(
        title=data.title,
        content=data.content,
        tags=data.tags,
        platform=data.platform,
        comment_guide=data.comment_guide,
        topic=data.topic,
        category=data.category,
        user_id=current_user.id,
        ai_record_id=data.ai_record_id,
    )
    return service.to_response(material)


@router.delete("/api/materials/{material_id}")
def delete_material(
    material_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PERM_MATERIALS_WRITE)),
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
    _: User = Depends(require_any_permission(PERM_PUBLISH_WRITE, PERM_MATERIALS_WRITE)),
):
    if data.kind not in {"text", "image"}:
        raise HTTPException(status_code=400, detail="kind 仅支持 text 或 image")
    details = build_prompt_details(
        data.kind,
        data.platform,
        data.topic,
        content_type=data.content_type,
        ratio=data.ratio,
        style=data.style,
        cover_text=data.cover_text,
        brand_color=data.brand_color,
        brand_hint=data.brand_hint,
    )
    return PromptBuildResponse(
        kind=data.kind,
        platform=data.platform,
        template_name=str(details["template_name"]),
        prompt=str(details["prompt_zh"]),
        prompt_zh=str(details["prompt_zh"]),
        prompt_en=details.get("prompt_en"),
        negative_prompt=details.get("negative_prompt"),
    )


@router.post("/api/ai/text/generate")
async def generate_text(
    data: TextGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_permission(PERM_PUBLISH_WRITE, PERM_MATERIALS_WRITE)),
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


# 快捷润色动作映射（与内容创作一致）
QUICK_ACTIONS: dict[str, str] = {
    "shorten": "请将文案缩短到原来的一半以内，保留核心信息",
    "expand": "请将文案扩写，增加更多细节和感情描述",
    "humorous": "请让文案更幽默有趣，增加网络热梗",
    "add_emoji": "请在合适位置添加适量的 emoji 表情",
    "formal": "请让文案更正式专业，减少口语化表达",
    "bilibili_style": "请调整为B站风格：口语化、有梗、二次元感、适合年轻受众",
    "xiaohongshu_style": "请调整为小红书风格：种草感、生活化、加emoji、分段落、标感叹号",
    "douyin_style": "请调整为抖音风格：短平快、有悬念、引导互动、加话题标签",
}


@router.post("/api/ai/text/polish")
async def polish_text(
    data: TextPolishRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_permission(PERM_PUBLISH_WRITE, PERM_MATERIALS_WRITE)),
):
    """按指令润色：基于已有文案 + 用户指令改写，不依赖创作 session。

    支持 quick_action（快捷风格）或自由 instruction（如"缩短到100字""第一句改抓人"）。
    """
    if not data.title and not data.body:
        raise HTTPException(status_code=400, detail="请先填写或生成待润色的文案")

    if data.quick_action and data.quick_action in QUICK_ACTIONS:
        instruction = QUICK_ACTIONS[data.quick_action]
    elif data.instruction:
        instruction = data.instruction
    else:
        instruction = "请润色优化此文案"

    prompt = f"""当前文案：
标题：{data.title}
正文：{data.body}
标签：{', '.join(data.tags)}

润色指令：{instruction}

请根据指令改写文案，保持与目标平台 {data.platform} 风格一致。返回格式：
标题：xxx
正文：xxx
标签：#tag1 #tag2"""

    from app.adapters.ai_text.openai_compatible import AiProviderError

    service = AiContentService(db)
    try:
        result = await service.generate_text(
            prompt,
            data.platform,
            current_user.id,
            data.content_type,
        )
        return {
            "title": result.get("title", data.title),
            "body": result.get("body", data.body),
            "tags": result.get("tags", data.tags),
        }
    except AiProviderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"文案润色失败: {exc}") from exc


@router.post("/api/ai/image/generate")
async def generate_image(
    data: ImageGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PERM_MATERIALS_WRITE)),
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
            style=data.style,
            brand_color=data.brand_color,
            brand_hint=data.brand_hint,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"文生图失败: {exc}") from exc


@router.post("/api/ai/video/generate")
async def generate_video(
    data: VideoGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PERM_PUBLISH_WRITE)),
):
    """AI 生成视频"""
    service = AiContentService(db)
    try:
        return await service.generate_video(
            topic=data.topic,
            platform=data.platform,
            duration=data.duration,
            resolution=data.resolution,
            fps=data.fps,
            image_url=data.image_url,
            user_id=current_user.id,
            avatar_id=data.avatar_id,
            avatar_type=data.avatar_type,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"视频生成失败: {exc}") from exc

