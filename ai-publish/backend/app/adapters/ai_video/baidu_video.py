"""百度文心一格/千帆 视频生成适配器

官方平台: https://console.bce.baidu.com/qianfan/overview
文档中心: https://cloud.baidu.com/doc/WENXINWORKSHOP/index.html

当前实现基于百度千帆 OpenAI-compatible 接口的常见模式：
- 通过 AK/SK 换取 access_token
- 提交任务 POST {base_url}/v1/videos/text2video
- 查询任务 GET  {base_url}/v1/videos/{task_id}

由于百度视频生成 API 端点可能变化，建议根据官方最新文档调整
baidu_video_base_url 与 baidu_video_model。
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


DEFAULT_BASE_URL = "https://qianfan.baidubce.com/v2"
TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"
POLL_INTERVAL = 5
MAX_POLL_ATTEMPTS = 120


class BaiduVideoAdapter:
    """百度文心一格/千帆视频生成适配器"""

    provider = "baidu_video"

    def __init__(self, model: str = "bilibili-index", base_url: str = DEFAULT_BASE_URL) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")

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
                msg = data.get("message") or data.get("error_msg") or "未知错误"
                raise RuntimeError(f"百度视频生成失败: {msg}")

            await asyncio.sleep(POLL_INTERVAL)

        raise TimeoutError("百度视频生成超时（超过 600 秒）")

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
        api_key = AiProviderConfigService().get_field_value("baidu_api_key")

        if not api_key:
            result = await StubVideoAdapter().generate(data)
            result.provider = self.provider
            result.prompt = data.topic
            return result

        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=120) as client:
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

            submit_url = f"{self.base_url}/v1/videos/text2video"
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
                raise RuntimeError(f"百度未返回 task_id: {result}")

            final = await self._poll_task(client, headers, task_id)

        video_url = (
            final.get("video_url")
            or final.get("url")
            or final.get("data", {}).get("video_url")
            or final.get("data", {}).get("url")
        )
        if not video_url:
            raise RuntimeError(f"百度任务成功但未返回视频 URL: {final}")

        video_content = await self._download_video(client, video_url)
        video_path, _ = storage.save_bytes(video_content, suffix=".mp4")
        thumbnail_path = await self._generate_thumbnail(video_path)

        # 参考价：约 0.4 元/秒（以官方 pricing 为准）
        cost = float(data.duration) * 0.4

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
