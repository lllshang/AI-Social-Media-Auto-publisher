"""可灵 AI (Kling) 视频生成适配器

官方平台: https://platform.klingai.com/
API 文档: https://platform.klingai.com/api-doc

当前实现基于可灵公开 API 的常见模式：
- 文生视频 POST /v1/videos/text2video
- 图生视频 POST /v1/videos/image2video
- 查询任务 GET  /v1/videos/{video_id}

认证方式: Bearer Token (从 https://platform.klingai.com/ 申请 API Key)
"""

import asyncio
import base64
import mimetypes
import pathlib
from typing import Any

import cv2
import httpx
import numpy as np

from app.adapters.base import VideoGenerateInput, VideoGenerateResult


API_BASE = "https://api.klingai.com"
TEXT2VIDEO_URL = f"{API_BASE}/v1/videos/text2video"
IMAGE2VIDEO_URL = f"{API_BASE}/v1/videos/image2video"

POLL_INTERVAL = 5  # 秒
MAX_POLL_ATTEMPTS = 120  # 最多 600 秒


class KlingVideoAdapter:
    """可灵 AI 视频生成适配器"""

    provider = "kling_video"

    def __init__(self, model: str = "kling-v1", base_url: str = API_BASE) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")

    def _headers(self, api_key: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    def _resolve_image(self, image_input: str | None) -> str | None:
        """本地文件 → base64 data URL，HTTP URL 直接返回"""
        if not image_input:
            return None
        if image_input.startswith(("http://", "https://", "data:")):
            return image_input
        path = pathlib.Path(image_input)
        if not path.exists():
            return image_input
        mime_type, _ = mimetypes.guess_type(str(path))
        if not mime_type:
            mime_type = "image/jpeg"
        with open(path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")
        return f"data:{mime_type};base64,{encoded}"

    def _resolve_aspect_ratio(self, resolution: str) -> str:
        mapping = {
            "720p": "16:9",
            "1080p": "16:9",
            "portrait": "9:16",
            "square": "1:1",
        }
        return mapping.get(resolution, "16:9")

    async def _poll_task(self, client: httpx.AsyncClient, headers: dict, video_id: str) -> dict[str, Any]:
        query_url = f"{self.base_url}/v1/videos/{video_id}"
        for _ in range(MAX_POLL_ATTEMPTS):
            resp = await client.get(query_url, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            status = data.get("data", {}).get("task_status", data.get("data", {}).get("status", ""))
            if status in ("succeed", "success", "SUCCEEDED"):
                return data
            if status in ("failed", "fail", "FAILED"):
                msg = data.get("data", {}).get("task_status_msg", data.get("message", "未知错误"))
                raise RuntimeError(f"可灵视频生成失败: {msg}")

            await asyncio.sleep(POLL_INTERVAL)

        raise TimeoutError("可灵视频生成超时（超过 600 秒）")

    async def _download_video(self, client: httpx.AsyncClient, video_url: str) -> bytes:
        resp = await client.get(video_url, timeout=120)
        resp.raise_for_status()
        return resp.content

    async def _generate_thumbnail(self, video_path: str) -> str:
        from app.adapters.factory import get_adapter_factory

        cap = cv2.VideoCapture(video_path)
        ret, frame = cap.read()
        cap.release()

        storage = get_adapter_factory().get_storage_adapter()
        if not ret:
            black = np.zeros((720, 1280, 3), dtype=np.uint8)
            _, thumbnail_bytes = cv2.imencode(".jpg", black)
        else:
            _, thumbnail_bytes = cv2.imencode(".jpg", frame)

        thumbnail_path, _ = storage.save_bytes(thumbnail_bytes.tobytes(), suffix=".jpg")
        return thumbnail_path

    async def generate(self, data: VideoGenerateInput) -> VideoGenerateResult:
        from app.adapters.ai_video.stub import StubVideoAdapter
        from app.adapters.factory import get_adapter_factory
        from app.services.ai_provider_config_service import AiProviderConfigService

        storage = get_adapter_factory().get_storage_adapter()
        api_key = AiProviderConfigService().get_field_value("kling_api_key")

        if not api_key:
            result = await StubVideoAdapter().generate(data)
            result.provider = self.provider
            result.prompt = data.topic
            return result

        headers = self._headers(api_key)
        aspect_ratio = self._resolve_aspect_ratio(data.resolution)

        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": data.topic,
            "aspect_ratio": aspect_ratio,
            "duration": data.duration,
        }

        # 图生视频
        is_image_to_video = bool(data.image_url)
        submit_url = IMAGE2VIDEO_URL if is_image_to_video else TEXT2VIDEO_URL
        if is_image_to_video:
            first_frame = self._resolve_image(data.image_url)
            if first_frame:
                payload["image"] = first_frame

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(submit_url, headers=headers, json=payload)
            resp.raise_for_status()
            result = resp.json()

            video_id = result.get("data", {}).get("video_id") or result.get("data", {}).get("task_id")
            if not video_id:
                raise RuntimeError(f"可灵未返回 video_id: {result}")

            final = await self._poll_task(client, headers, video_id)

        video_url = final.get("data", {}).get("video_url") or final.get("data", {}).get("url")
        if not video_url:
            raise RuntimeError(f"可灵任务成功但未返回视频 URL: {final}")

        video_content = await self._download_video(client, video_url)
        video_path, _ = storage.save_bytes(video_content, suffix=".mp4")
        thumbnail_path = await self._generate_thumbnail(video_path)

        # 可灵约 0.25 元/秒（参考价，以官方为准）
        cost = float(data.duration) * 0.25

        return VideoGenerateResult(
            video_paths=[video_path],
            thumbnail_paths=[thumbnail_path],
            provider=self.provider,
            prompt=data.topic,
            cost=cost,
            duration=float(data.duration),
            metadata={
                "video_id": video_id,
                "model": self.model,
                "aspect_ratio": aspect_ratio,
                "mode": "image2video" if is_image_to_video else "text2video",
            },
        )
