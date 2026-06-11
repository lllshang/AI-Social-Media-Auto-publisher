from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from loguru import logger
from sqlalchemy.orm import Session

from app.adapters.factory import get_adapter_factory
from app.models import Material, PublishTask
from app.services.system_config_service import SystemConfigService


class MaterialCleanupService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.config = SystemConfigService(db)
        self.storage = get_adapter_factory().get_storage_adapter()

    def cleanup_enabled(self) -> bool:
        return self.config.get_bool("material_cleanup_enabled", False)

    def retention_days(self) -> int:
        return max(1, self.config.get_int("material_retention_days", 90))

    def _referenced_ids(self) -> set[int]:
        referenced: set[int] = set()
        for task in self.db.query(PublishTask).all():
            for material_id in task.material_ids or []:
                try:
                    referenced.add(int(material_id))
                except (TypeError, ValueError):
                    continue
        return referenced

    def run_cleanup(self) -> dict[str, int]:
        if not self.cleanup_enabled():
            return {"removed": 0, "skipped": 0}

        cutoff = datetime.utcnow() - timedelta(days=self.retention_days())
        referenced = self._referenced_ids()
        removed = 0
        skipped = 0

        candidates = (
            self.db.query(Material)
            .filter(Material.created_at < cutoff)
            .filter(Material.status.in_(["active", "deleted"]))
            .all()
        )
        for material in candidates:
            if material.id in referenced:
                skipped += 1
                continue
            if self._remove_material_files(material):
                removed += 1
            else:
                skipped += 1
            self.db.delete(material)

        self.db.commit()
        if removed:
            logger.info("素材清理完成：移除 {} 条，跳过 {}", removed, skipped)
        return {"removed": removed, "skipped": skipped}

    def _remove_material_files(self, material: Material) -> bool:
        removed_any = False
        for path_str in (material.file_path, material.thumbnail):
            if not path_str:
                continue
            path = Path(path_str)
            if path.exists():
                try:
                    path.unlink()
                    removed_any = True
                except OSError:
                    logger.warning("无法删除文件: {}", path)
        return removed_any
