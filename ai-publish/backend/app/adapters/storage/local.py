import uuid
from pathlib import Path

from app.adapters.base import StorageAdapter
from app.config import get_settings


class LocalStorageAdapter(StorageAdapter):
    def __init__(self) -> None:
        self.settings = get_settings()
        self.base_path = self.settings.storage_path

    def save_bytes(self, content: bytes, suffix: str = ".bin") -> tuple[str, str]:
        filename = f"{uuid.uuid4().hex}{suffix}"
        file_path = self.base_path / filename
        file_path.write_bytes(content)
        return str(file_path), self.get_url(str(file_path))

    def save_file(self, source_path: str, suffix: str | None = None) -> tuple[str, str]:
        src = Path(source_path)
        ext = suffix or src.suffix or ".bin"
        filename = f"{uuid.uuid4().hex}{ext}"
        dest = self.base_path / filename
        dest.write_bytes(src.read_bytes())
        return str(dest), self.get_url(str(dest))

    def get_url(self, file_path: str) -> str:
        name = Path(file_path).name
        return f"/static/materials/{name}"
