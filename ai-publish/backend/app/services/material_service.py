import json
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.adapters.base import ImageGenerateInput, TextGenerateInput
from app.adapters.factory import get_adapter_factory
from app.models import AiGenerationRecord, Material
from app.schemas import MaterialResponse
from app.services.image_moderation_service import ImageModerationService
from app.utils.thumbnail import generate_image_thumbnail


class MaterialService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.factory = get_adapter_factory()

    def to_response(self, material: Material, *, include_text_body: bool = False) -> MaterialResponse:
        storage = self.factory.get_storage_adapter()
        thumbnail_url = storage.get_url(material.thumbnail) if material.thumbnail else None
        text_preview = None
        text_content = None
        if material.type == "text":
            body = self._read_text_body(material.file_path)
            if body:
                text_preview = body[:200]
                if include_text_body:
                    text_content = body
        return MaterialResponse(
            id=material.id,
            type=material.type,
            source=material.source,
            name=material.name,
            category=material.category,
            file_path=material.file_path,
            url=material.url,
            thumbnail_url=thumbnail_url,
            text_preview=text_preview,
            text_content=text_content,
            moderation_status=material.moderation_status,
            moderation_detail=material.moderation_detail,
            created_at=material.created_at,
        )

    @staticmethod
    def _read_text_body(file_path: str) -> str | None:
        path = Path(file_path)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return str(payload.get("content") or "")
        except (OSError, json.JSONDecodeError, TypeError):
            return None

    def _attach_thumbnail(self, material: Material) -> None:
        if material.type != "image":
            return
        storage = self.factory.get_storage_adapter()
        thumb_path = generate_image_thumbnail(material.file_path, storage)
        if thumb_path:
            material.thumbnail = thumb_path

    def get(self, material_id: int) -> Material | None:
        return self.db.query(Material).filter(Material.id == material_id, Material.status == "active").first()

    def get_any(self, material_id: int) -> Material | None:
        return self.db.query(Material).filter(Material.id == material_id).first()

    def delete_material(self, material_id: int) -> None:
        material = self.get(material_id)
        if not material:
            raise ValueError("素材不存在")
        material.status = "deleted"
        self.db.commit()

    def list_materials(
        self,
        material_type: str | None = None,
        category: str | None = None,
        keyword: str | None = None,
    ) -> list[Material]:
        query = self.db.query(Material).filter(Material.status == "active")
        if material_type:
            query = query.filter(Material.type == material_type)
        if category:
            query = query.filter(Material.category == category)
        if keyword:
            like = f"%{keyword}%"
            query = query.filter(
                (Material.name.like(like)) | (Material.file_path.like(like))
            )
        return query.order_by(Material.id.desc()).all()

    def list_categories(self) -> list[str]:
        rows = (
            self.db.query(Material.category)
            .filter(Material.status == "active", Material.category.isnot(None), Material.category != "")
            .distinct()
            .all()
        )
        return sorted({row[0] for row in rows if row[0]})

    async def upload(
        self,
        file: UploadFile,
        user_id: int | None = None,
        name: str | None = None,
        category: str | None = None,
    ) -> Material:
        suffix = Path(file.filename or "upload.bin").suffix or ".bin"
        content = await file.read()
        material_type = "video" if suffix.lower() in {".mp4", ".mov", ".avi"} else "image"
        storage = self.factory.get_storage_adapter()
        file_path, url = storage.save_bytes(content, suffix=suffix)
        material = Material(
            type=material_type,
            source="upload",
            file_path=file_path,
            url=url,
            name=name or Path(file.filename or "upload").stem,
            category=category or "默认",
            created_by=user_id,
        )
        self._attach_thumbnail(material)
        self.db.add(material)
        self.db.commit()
        self.db.refresh(material)
        if material.type == "image":
            await ImageModerationService(self.db).apply_to_material(material)
            self.db.commit()
            self.db.refresh(material)
        return material

    def save_text_draft(
        self,
        *,
        title: str,
        content: str,
        tags: list[str] | None = None,
        platform: str = "xhs",
        comment_guide: str | None = None,
        topic: str | None = None,
        category: str | None = None,
        user_id: int | None = None,
        ai_record_id: int | None = None,
    ) -> Material:
        payload = {
            "title": title,
            "content": content,
            "tags": tags or [],
            "platform": platform,
            "comment_guide": comment_guide,
            "topic": topic,
        }
        storage = self.factory.get_storage_adapter()
        file_path, _ = storage.save_bytes(
            json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            suffix=".json",
        )
        material = Material(
            type="text",
            source="draft",
            file_path=file_path,
            name=title,
            category=category or "文案草稿",
            ai_record_id=ai_record_id,
            created_by=user_id,
        )
        self.db.add(material)
        self.db.commit()
        self.db.refresh(material)
        return material

    def create_from_ai_paths(
        self,
        image_paths: list[str],
        ai_record_id: int | None = None,
        user_id: int | None = None,
    ) -> list[Material]:
        storage = self.factory.get_storage_adapter()
        materials: list[Material] = []
        for path in image_paths:
            material = Material(
                type="image",
                source="ai_generated",
                file_path=path,
                url=storage.get_url(path),
                ai_record_id=ai_record_id,
                created_by=user_id,
            )
            self._attach_thumbnail(material)
            self.db.add(material)
            materials.append(material)
        self.db.commit()
        for material in materials:
            self.db.refresh(material)
        return materials

    def validate_material_ids(self, material_ids: list[int], content_type: str) -> list[Material]:
        materials = []
        for material_id in material_ids:
            material = self.get(material_id)
            if not material:
                raise ValueError(f"素材不存在: {material_id}")
            if content_type == "note" and material.type != "image":
                raise ValueError(f"图文任务需要图片素材: {material_id}")
            if content_type == "video" and material.type not in {"video", "image"}:
                raise ValueError(f"视频任务素材类型无效: {material_id}")
            materials.append(material)
        if content_type == "video" and not any(m.type == "video" for m in materials):
            raise ValueError("视频任务需要至少一个视频素材")
        ImageModerationService(self.db).assert_images_allowed(materials)
        return materials


class AiContentService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.factory = get_adapter_factory()
        self.material_service = MaterialService(db)

    async def generate_text(
        self,
        topic: str,
        platform: str,
        user_id: int | None = None,
        content_type: str = "note",
    ) -> dict:
        adapter = self.factory.get_ai_text_adapter()
        result = await adapter.generate(
            TextGenerateInput(topic=topic, platform=platform, content_type=content_type)
        )
        record = AiGenerationRecord(
            type="text",
            provider=result.provider,
            prompt=result.prompt,
            result_summary=f"title={result.title}",
            cost=result.cost,
            created_by=user_id,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return {
            "record_id": record.id,
            "title": result.title,
            "content": result.content,
            "tags": result.tags,
            "cover_text": result.cover_text,
            "comment_guide": result.comment_guide,
            "provider": result.provider,
            "model": getattr(adapter, "model", None),
            "cost": float(result.cost),
        }

    async def generate_image(
        self,
        topic: str,
        platform: str,
        ratio: str = "3:4",
        count: int = 1,
        cover_text: str | None = None,
        user_id: int | None = None,
        *,
        style: str = "default",
        brand_color: str | None = None,
        brand_hint: str | None = None,
    ) -> dict:
        adapter = self.factory.get_ai_image_adapter()
        result = await adapter.generate(
            ImageGenerateInput(
                topic=topic,
                platform=platform,
                ratio=ratio,
                count=count,
                cover_text=cover_text,
                style=style,
                brand_color=brand_color,
                brand_hint=brand_hint,
            )
        )
        import json

        record = AiGenerationRecord(
            type="image",
            provider=result.provider,
            prompt=result.prompt,
            result_summary=json.dumps(
                {
                    "images": len(result.image_paths),
                    "style": style,
                    "ratio": ratio,
                    "brand_color": brand_color,
                    "brand_hint": brand_hint,
                    "negative_prompt": result.negative_prompt,
                },
                ensure_ascii=False,
            ),
            cost=result.cost,
            created_by=user_id,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        materials = self.material_service.create_from_ai_paths(
            result.image_paths,
            ai_record_id=record.id,
            user_id=user_id,
        )
        moderation = ImageModerationService(self.db)
        for material in materials:
            await moderation.apply_to_material(material)
        self.db.commit()
        for material in materials:
            self.db.refresh(material)
        return {
            "record_id": record.id,
            "materials": [{"id": m.id, "url": m.url, "file_path": m.file_path} for m in materials],
            "provider": result.provider,
            "model": getattr(adapter, "model", None),
            "prompt": result.prompt,
            "style": style,
            "brand_color": brand_color,
            "brand_hint": brand_hint,
            "cost": float(result.cost),
        }
