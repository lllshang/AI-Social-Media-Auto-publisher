from app.adapters.base import AiImageAdapter, AiTextAdapter, PlatformAdapter, StorageAdapter
from app.adapters.platform.xhs import XhsPlatformAdapter
from app.adapters.storage.local import LocalStorageAdapter
from app.adapters.storage.stub import StubStorageAdapter
from app.config import get_settings


class AdapterFactory:
    def __init__(self) -> None:
        self.settings = get_settings()

    def get_platform_adapter(self, platform: str) -> PlatformAdapter:
        registry: dict[str, type[PlatformAdapter]] = {
            "xhs": XhsPlatformAdapter,
        }
        adapter_cls = registry.get(platform)
        if not adapter_cls:
            raise ValueError(f"Unsupported platform: {platform}")
        return adapter_cls()

    def get_ai_text_adapter(self) -> AiTextAdapter:
        from app.services.ai_model_service import AiModelService

        return AiModelService().get_text_adapter()

    def get_ai_image_adapter(self) -> AiImageAdapter:
        from app.services.ai_model_service import AiModelService

        return AiModelService().get_image_adapter()

    def get_storage_adapter(self) -> StorageAdapter:
        registry: dict[str, type[StorageAdapter]] = {
            "local": LocalStorageAdapter,
            "stub": StubStorageAdapter,
        }
        adapter_cls = registry.get(self.settings.storage)
        if not adapter_cls:
            raise ValueError(f"Unsupported storage: {self.settings.storage}")
        return adapter_cls()


_factory: AdapterFactory | None = None


def get_adapter_factory() -> AdapterFactory:
    global _factory
    if _factory is None:
        _factory = AdapterFactory()
    return _factory
