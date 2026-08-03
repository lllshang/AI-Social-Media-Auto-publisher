import sys
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any


@dataclass
class LoginResult:
    success: bool
    status: str
    message: str
    qrcode_path: str | None = None
    qrcode_data_url: str | None = None


@dataclass
class PublishContext:
    task_id: int
    platform: str
    account_id: int
    account_name: str
    cookie_file: str
    title: str
    content: str
    tags: list[str] = field(default_factory=list)
    content_type: str = "note"
    material_paths: list[str] = field(default_factory=list)
    thumbnail_path: str | None = None
    cover_text: str | None = None
    publish_time: datetime | None = None
    bilibili_tid: int | None = None
    publish_proxy: str | None = None
    log_callback: Any | None = None


@dataclass
class PublishResult:
    success: bool
    message: str
    platform_ref: str | None = None


@dataclass
class TextGenerateInput:
    topic: str
    platform: str = "xhs"
    content_type: str = "note"
    style: str = "default"


@dataclass
class TextGenerateResult:
    title: str
    content: str
    tags: list[str]
    cover_text: str
    provider: str
    prompt: str
    comment_guide: str = ""
    cost: float = 0.0


@dataclass
class ImageGenerateInput:
    topic: str
    platform: str = "xhs"
    ratio: str = "3:4"
    style: str = "default"
    count: int = 1
    cover_text: str | None = None
    brand_color: str | None = None
    brand_hint: str | None = None


@dataclass
class ImageGenerateResult:
    image_paths: list[str]
    provider: str
    prompt: str
    cost: float = 0.0
    negative_prompt: str | None = None
    elapsed: float = 0.0


@dataclass
class VideoGenerateInput:
    topic: str
    platform: str = "douyin"
    duration: int = 5
    resolution: str = "720p"
    fps: int = 24
    style: str = "default"
    image_url: str | None = None
    count: int = 1
    avatar_id: int | None = None
    avatar_type: str | None = None  # digital_human | simulation_human


@dataclass
class VideoGenerateResult:
    video_paths: list[str]
    thumbnail_paths: list[str]
    provider: str
    prompt: str
    cost: float = 0.0
    duration: float = 0.0
    elapsed: float = 0.0
    metadata: dict = field(default_factory=dict)


class PlatformAdapter(Protocol):
    async def login(self, account_id: int, account_name: str, cookie_file: str) -> LoginResult: ...
    async def check_cookie_valid(self, cookie_file: str) -> bool: ...
    async def publish(self, context: PublishContext) -> PublishResult: ...


class AiTextAdapter(Protocol):
    async def generate(self, data: TextGenerateInput) -> TextGenerateResult: ...


class AiImageAdapter(Protocol):
    async def generate(self, data: ImageGenerateInput) -> ImageGenerateResult: ...


class AiVideoAdapter(Protocol):
    async def generate(self, data: VideoGenerateInput) -> VideoGenerateResult: ...


class StorageAdapter(ABC):
    @abstractmethod
    def save_bytes(self, content: bytes, suffix: str = ".bin") -> tuple[str, str]:
        """Return (file_path, public_url)."""

    @abstractmethod
    def save_file(self, source_path: str, suffix: str | None = None) -> tuple[str, str]:
        """Return (file_path, public_url)."""

    @abstractmethod
    def get_url(self, file_path: str) -> str:
        ...
