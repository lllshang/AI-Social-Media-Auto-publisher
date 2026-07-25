"""即梦 Dreamina / 火山 Seedance 视频生成适配器

官方平台: https://dreamina.capcut.com/
企业级 API 通常通过火山引擎 (https://www.volcengine.com/) 或方舟平台开放。

当前实现为通用 OpenAI/火山风格异步任务适配器，默认 endpoint:
- 提交任务 POST {base_url}/v1/videos/generations
- 查询任务 GET  {base_url}/v1/videos/{task_id}

由于官方视频 API 端点可能变化，强烈建议在使用前根据火山引擎官方文档
确认 endpoint，并通过后台 "模型配置" 修改 dreamina_base_url 与 dreamina_model。
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


DEFAULT_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
POLL_INTERVAL = 5
MAX_POLL_ATTEMPTS = 120


class DreaminaVideoAdapter:
    """即梦 Dreamina 视频生成适配器"""

    provider = "dreamina_video"

    def __init__(self, model: str = "seedance-2.0", base_url: str = DEFAULT_BASE_URL) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")

    def _headers(self, api_key: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    def _resolve_image(self, image_input: str | None) -> str | None:
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

    def _resolve_size(self, resolution: str) -> str:
        mapping = {
            "720p": "1280x720",
            "1080p": "1920x1080",
            "portrait": "720x1280",
            "square": "1024x1024",
        }
        return mapping.get(resolution, "1280x720")

    async def _poll_task(self, client: httpx.AsyncClient, headers: dict, task_id: str) -> dict[str, Any]:
        query_url = f"{self.base_url}/v1/videos/{task_id}"
        for _ in range(MAX_POLL_ATTEMPTS):
            resp = await client.get(query_url, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            status = data.get("status") or data.get("task_status") or data.get("data", {}).get("status")
            if status in ("succeed", "success", "SUCCEEDED", "completed"):
                return data
            if status in ("failed", "fail", "FAILED", "error"):
                msg = data.get("message") or data.get("error", {}).get("message", "未知错误")
                raise RuntimeError(f"即梦视频生成失败: {msg}")

            await asyncio.sleep(POLL_INTERVAL)

        raise TimeoutError("即梦视频生成超时（超过 600 秒）")

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
        api_key = AiProviderConfigService().get_field_value("dreamina_api_key")

        if not api_key:
            result = await StubVideoAdapter().generate(data)
            result.provider = self.provider
            result.prompt = data.topic
            return result

        headers = self._headers(api_key)
        size = self._resolve_size(data.resolution)

        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": data.topic,
            "size": size,
            "duration": data.duration,
        }

        image_url = self._resolve_image(data.image_url)
        if image_url:
            payload["image"] = image_url

        submit_url = f"{self.base_url}/v1/videos/generations"

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(submit_url, headers=headers, json=payload)
            resp.raise_for_status()
            result = resp.json()

            task_id = (
                result.get("id")
                or result.get("task_id")
                or result.get("data", {}).get("id")
                or result.get("data", {}).get("task_id")
            )
            if not task_id:
                raise RuntimeError(f"即梦未返回 task_id: {result}")

            final = await self._poll_task(client, headers, task_id)

        video_url = (
            final.get("video_url")
            or final.get("url")
            or final.get("data", {}).get("video_url")
            or final.get("data", {}).get("url")
        )
        if not video_url:
            raise RuntimeError(f"即梦任务成功但未返回视频 URL: {final}")

        video_content = await self._download_video(client, video_url)
        video_path, _ = storage.save_bytes(video_content, suffix=".mp4")
        thumbnail_path = await self._generate_thumbnail(video_path)

        # 参考价：约 0.3 元/秒（以官方 pricing 为准）
        cost = float(data.duration) * 0.3

        return VideoGenerateResult(
            video_paths=[video_path],
            thumbnail_paths=[thumbnail_path],
            provider=self.provider,
            prompt=data.topic,
            cost=cost,
            duration=float(data.duration),
            metadata={
                "task_id": task_id,
                "model": self.model,
                "size": size,
                "mode": "image2video" if image_url else "text2video",
            },
        )
