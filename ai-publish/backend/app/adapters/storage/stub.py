from app.adapters.base import StorageAdapter


class StubStorageAdapter(StorageAdapter):
    def save_bytes(self, content: bytes, suffix: str = ".bin") -> tuple[str, str]:
        return f"/tmp/stub{suffix}", f"/static/materials/stub{suffix}"

    def save_file(self, source_path: str, suffix: str | None = None) -> tuple[str, str]:
        ext = suffix or ".bin"
        return f"/tmp/stub{ext}", f"/static/materials/stub{ext}"

    def get_url(self, file_path: str) -> str:
        return file_path
