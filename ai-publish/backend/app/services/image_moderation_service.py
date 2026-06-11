from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.models import Material
from app.services.image_moderation.providers import (
    PAID_PROVIDERS,
    PROVIDER_REGISTRY,
    ModerationOutcome,
    build_provider,
)
from app.services.system_config_service import SystemConfigService


class ImageModerationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.config = SystemConfigService(db)

    def enabled(self) -> bool:
        return self.config.image_moderation_enabled()

    def provider_name(self) -> str:
        raw = (self.config.image_moderation_provider() or "stub").strip().lower()
        return raw if raw in PROVIDER_REGISTRY else "stub"

    def is_paid_provider(self, name: str | None = None) -> bool:
        return (name or self.provider_name()) in PAID_PROVIDERS

    def get_provider(self):
        return build_provider(self.provider_name(), self.config)

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
                {"provider": "disabled", "message": "图片审核未开启", "billable": False},
                ensure_ascii=False,
            )
            return material

        material.moderation_status = "pending"
        outcome: ModerationOutcome = await self.get_provider().moderate(material.file_path)
        material.moderation_status = "passed" if outcome.passed else "rejected"
        material.moderation_detail = json.dumps(outcome.to_detail(), ensure_ascii=False)
        return material
