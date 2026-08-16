"""本机 Worker 与服务器共用的发布执行器（不依赖服务器本地素材路径）。"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path

from app.adapters.base import PublishContext, PublishResult
from app.adapters.factory import get_adapter_factory
from app.utils.vendor_proxy import use_account_proxy


LogCallback = Callable[[str, str, str], Awaitable[None]]


class WorkerPublishRunner:
    def __init__(self) -> None:
        self.factory = get_adapter_factory()

    async def run(
        self,
        *,
        task_id: int,
        platform: str,
        account_id: int,
        account_name: str,
        cookie_file: str,
        title: str,
        content: str,
        tags: list[str],
        content_type: str,
        material_paths: list[str],
        thumbnail_path: str | None,
        cover_text: str | None,
        publish_time: datetime | None,
        bilibili_tid: int | None,
        publish_proxy: str | None,
        log_callback: LogCallback | None = None,
    ) -> PublishResult:
        context = PublishContext(
            task_id=task_id,
            platform=platform,
            account_id=account_id,
            account_name=account_name,
            cookie_file=cookie_file,
            title=title,
            content=content,
            tags=tags,
            content_type=content_type,
            material_paths=material_paths,
            thumbnail_path=thumbnail_path,
            cover_text=cover_text,
            publish_time=publish_time,
            bilibili_tid=bilibili_tid,
            publish_proxy=publish_proxy,
            log_callback=log_callback,
        )
        # 任务已由服务器校验并派发，本机 Worker 无需重复配置 BILIBILI_ENABLED
        adapter = self.factory.get_platform_adapter(platform, trust_server=True)
        with use_account_proxy(publish_proxy):
            return await adapter.publish(context)
