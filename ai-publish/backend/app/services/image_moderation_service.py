from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import Material
from app.services.system_config_service import SystemConfigService


@dataclass
class ModerationOutcome:
    passed: bool
    provider: str
    message: str
    labels: list[str] | None = None

    def to_detail(self) -> dict:
        return {
            "provider": self.provider,
            "message": self.message,
            "labels": self.labels or [],
        }


class ImageModerationProvider(ABC):
    @abstractmethod
    async def moderate(self, file_path: str) -> ModerationOutcome:
        raise NotImplementedError


class StubImageModerationProvider(ImageModerationProvider):
    async def moderate(self, file_path: str) -> ModerationOutcome:
        path = Path(file_path)
        if not path.exists():
            return ModerationOutcome(
                passed=False,
                provider="stub",
                message="图片文件不存在",
            )
        return ModerationOutcome(
            passed=True,
            provider="stub",
            message="Stub 审核通过（开发/未接云 API 时默认放行）",
        )


class ImageModerationService:
    PROVIDERS: dict[str, type[ImageModerationProvider]] = {
        "stub": StubImageModerationProvider,
    }

    def __init__(self, db: Session) -> None:
        self.db = db
        self.config = SystemConfigService(db)

    def enabled(self) -> bool:
        return self.config.image_moderation_enabled()

    def provider_name(self) -> str:
        raw = (self.config.image_moderation_provider() or "stub").strip().lower()
        return raw if raw in self.PROVIDERS else "stub"

    def get_provider(self) -> ImageModerationProvider:
        return self.PROVIDERS[self.provider_name()]()

    def is_image_allowed(self, material: Material) -> bool:
        if material.type != "image":
            return True
        if not self.enabled():
            return True
        status = material.moderation_status
        return status in {None, "passed", "skipped"}

    def assert_images_allowed(self, materials: list[Material]) -> None:
        if not self.enabled():
            return
        for material in materials:
            if material.type != "image":
                continue
            status = material.moderation_status
            if status in {None, "passed", "skipped"}:
                continue
            name = material.name or f"#{material.id}"
            if status == "pending":
                raise ValueError(f"图片素材「{name}」审核中，请稍后再提交")
            if status == "rejected":
                raise ValueError(f"图片素材「{name}」未通过内容审核")

    async def apply_to_material(self, material: Material) -> Material:
        if material.type != "image":
            return material
        if not self.enabled():
            material.moderation_status = "skipped"
            material.moderation_detail = json.dumps(
                {"provider": "disabled", "message": "图片审核未开启"},
                ensure_ascii=False,
            )
            return material

        material.moderation_status = "pending"
        outcome = await self.get_provider().moderate(material.file_path)
        material.moderation_status = "passed" if outcome.passed else "rejected"
        material.moderation_detail = json.dumps(outcome.to_detail(), ensure_ascii=False)
        return material
