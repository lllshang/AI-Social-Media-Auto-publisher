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
        # 计算 file_path 相对于 base_path 的子路径，保留 voices/ 等子目录，
        # 否则 voices/avatar_xxx.mp3 会被截断为 /static/materials/avatar_xxx.mp3，
        # 实际文件却在 voices/ 下，访问 404。
        p = Path(file_path)
        try:
            rel = p.relative_to(self.base_path)
        except ValueError:
            # 兜底：不在 base_path 下时只用文件名
            return f"/static/materials/{p.name}"
        return f"/static/materials/{rel.as_posix()}"
