import shutil
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.adapters.base import ImageGenerateInput, TextGenerateInput
from app.adapters.factory import get_adapter_factory
from app.models import AiGenerationRecord, Material


class MaterialService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.factory = get_adapter_factory()

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
            if content_type == "video" and material.type != "video":
                raise ValueError(f"视频任务需要视频素材: {material_id}")
            materials.append(material)
        return materials


class AiContentService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.factory = get_adapter_factory()
        self.material_service = MaterialService(db)

    async def generate_text(self, topic: str, platform: str, user_id: int | None = None) -> dict:
        adapter = self.factory.get_ai_text_adapter()
        result = await adapter.generate(TextGenerateInput(topic=topic, platform=platform))
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
    ) -> dict:
        image_topic = topic
        if cover_text:
            image_topic = f"{topic}，封面文字：{cover_text}"
        adapter = self.factory.get_ai_image_adapter()
        result = await adapter.generate(
            ImageGenerateInput(
                topic=image_topic,
                platform=platform,
                ratio=ratio,
                count=count,
                cover_text=cover_text,
            )
        )
        record = AiGenerationRecord(
            type="image",
            provider=result.provider,
            prompt=result.prompt,
            result_summary=f"images={len(result.image_paths)}",
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
        return {
            "record_id": record.id,
            "materials": [{"id": m.id, "url": m.url, "file_path": m.file_path} for m in materials],
            "provider": result.provider,
            "model": getattr(adapter, "model", None),
            "prompt": result.prompt,
            "cost": float(result.cost),
        }
