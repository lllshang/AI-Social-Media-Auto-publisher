"""S3 兼容对象存储（腾讯云 COS / 阿里云 OSS / MinIO）。"""

from __future__ import annotations

import uuid
from pathlib import Path
import boto3
from botocore.client import Config

from app.adapters.base import StorageAdapter
from app.config import get_settings


class ObjectStorageAdapter(StorageAdapter):
    def __init__(self) -> None:
        self.settings = get_settings()
        if not self.settings.object_storage_bucket:
            raise ValueError("未配置 OBJECT_STORAGE_BUCKET")
        if not self.settings.object_storage_access_key or not self.settings.object_storage_secret_key:
            raise ValueError("未配置对象存储 AccessKey/SecretKey")

        self.bucket = self.settings.object_storage_bucket
        self.public_base_url = (self.settings.object_storage_public_base_url or "").rstrip("/")
        self.client = boto3.client(
            "s3",
            endpoint_url=self.settings.object_storage_endpoint,
            aws_access_key_id=self.settings.object_storage_access_key,
            aws_secret_access_key=self.settings.object_storage_secret_key,
            region_name=self.settings.object_storage_region or None,
            config=Config(signature_version="s3v4", s3={"addressing_style": self.settings.object_storage_addressing_style}),
        )

    def _object_key(self, suffix: str) -> str:
        prefix = self.settings.object_storage_prefix.strip("/")
        filename = f"{uuid.uuid4().hex}{suffix}"
        return f"{prefix}/{filename}" if prefix else filename

    def _build_url(self, key: str) -> str:
        if self.public_base_url:
            return f"{self.public_base_url}/{key}"
        endpoint = (self.settings.object_storage_endpoint or "").rstrip("/")
        if endpoint:
            return f"{endpoint}/{self.bucket}/{key}"
        return f"/{self.bucket}/{key}"

    def save_bytes(self, content: bytes, suffix: str = ".bin") -> tuple[str, str]:
        key = self._object_key(suffix)
        self.client.put_object(Bucket=self.bucket, Key=key, Body=content)
        return key, self._build_url(key)

    def save_file(self, source_path: str, suffix: str | None = None) -> tuple[str, str]:
        src = Path(source_path)
        ext = suffix or src.suffix or ".bin"
        content = src.read_bytes()
        return self.save_bytes(content, ext)

    def get_url(self, file_path: str) -> str:
        if file_path.startswith("http://") or file_path.startswith("https://"):
            return file_path
        if file_path.startswith("/static/materials/"):
            name = Path(file_path).name
            return self._build_url(name)
        return self._build_url(file_path.lstrip("/"))
