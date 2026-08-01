"""即梦 Dreamina / 火山 Seedance 视频生成适配器

官方平台: https://dreamina.capcut.com/
企业级 API 通常通过火山引擎方舟平台开放：https://www.volcengine.com/

当前实现对接火山方舟原生异步任务 API：
- 提交任务 POST {base_url}/contents/generations/tasks
- 查询任务 GET  {base_url}/contents/generations/tasks/{task_id}

火山方舟视频生成要求 model 字段填写「推理接入点/Endpoint ID」（通常以 ep- 开头），
因此强烈建议在后台配置 dreamina_model，未配置时默认使用 seedance-2.0。
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
    """即梦 Dreamina 视频生成适配器（火山方舟原生 API）"""

    provider = "dreamina_video"

    def __init__(self, model: str = "doubao-seedance-2-0-mini-260615", base_url: str = DEFAULT_BASE_URL) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.submit_url = f"{self.base_url}/contents/generations/tasks"
        self.poll_url_tpl = f"{self.base_url}/contents/generations/tasks/{{task_id}}"

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

    def _resolve_ratio(self, resolution: str) -> str:
        r = (resolution or "").lower()
        if "3:4" in r:
            return "3:4"
        if "9:16" in r or "竖" in r or "portrait" in r or "720x1280" in r:
            return "9:16"
        if "1:1" in r or "square" in r or "1024x1024" in r:
            return "1:1"
        if "16:9" in r or "landscape" in r or "横" in r or "1280x720" in r or "1920x1080" in r:
            return "16:9"
        return "16:9"

    def _resolve_resolution(self, resolution: str) -> str:
        r = (resolution or "").lower()
        if "1080" in r:
            return "1080p"
        if "480" in r:
            return "480p"
        return "720p"

    def _build_content(self, data: VideoGenerateInput) -> list[dict[str, Any]]:
        """构造火山方舟 content 数组，支持文生视频与图生视频。"""
        content: list[dict[str, Any]] = [{"type": "text", "text": data.topic}]

        image_url = self._resolve_image(data.image_url)
        if image_url:
            content.append({"type": "image_url", "image_url": {"url": image_url}, "role": "first_frame"})

        return content

    async def _poll_task(self, client: httpx.AsyncClient, headers: dict, task_id: str) -> dict[str, Any]:
        query_url = self.poll_url_tpl.format(task_id=task_id)
        for _ in range(MAX_POLL_ATTEMPTS):
            resp = await client.get(query_url, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            status = (data.get("status") or data.get("task_status") or data.get("data", {}).get("status") or "").lower()
            if status in ("succeeded", "succeed", "success", "completed"):
                return data
            if status in ("failed", "fail", "error", "cancelled", "canceled"):
                msg = (data.get("error", {}).get("message")
                       or data.get("message")
                       or data.get("status", {}).get("message")
                       or "未知错误")
                raise RuntimeError(f"即梦视频生成失败: {msg}")
            # running, queued, pending, processing — 继续轮询

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

    def _extract_video_url(self, data: dict[str, Any]) -> str | None:
        """从火山方舟响应中提取视频 URL，兼容多种字段布局。"""
        # 1. 新格式：content 为 dict / content 为 list
        content = data.get("content") or data.get("data", {}).get("content")
        if isinstance(content, dict):
            url = content.get("video_url") or content.get("url")
            if url:
                return url
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict):
                    url = item.get("video_url") or item.get("url")
                    if url:
                        return url

        # 2. 常见字段
        for key in ("video_url", "url", "video"):
            value = data.get(key) or data.get("data", {}).get(key)
            if isinstance(value, str):
                return value

        # 3. data 数组
        arr = data.get("data") or data.get("videos")
        if isinstance(arr, list) and arr:
            first = arr[0]
            if isinstance(first, dict):
                return first.get("video_url") or first.get("url") or first.get("video")

        return None

    async def generate(self, data: VideoGenerateInput) -> VideoGenerateResult:
        from app.adapters.ai_video.stub import StubVideoAdapter
        from app.adapters.factory import get_adapter_factory
        from app.services.ai_provider_config_service import AiProviderConfigService

        storage = get_adapter_factory().get_storage_adapter()
        config = AiProviderConfigService()
        api_key = config.get_field_value("dreamina_api_key")
        # 火山方舟 Key 通用，未单独配置 dreamina 时复用 doubao (火山) Key
        if not api_key:
            api_key = config.get_field_value("doubao_api_key")

        if not api_key:
            result = await StubVideoAdapter().generate(data)
            result.provider = self.provider
            result.prompt = data.topic
            return result

        headers = self._headers(api_key)
        payload: dict[str, Any] = {
            "model": self.model,
            "content": self._build_content(data),
            "resolution": self._resolve_resolution(data.resolution),
            "ratio": self._resolve_ratio(data.resolution),
            "duration": data.duration,
            "fps": data.fps,
            "generate_audio": True,
        }

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(self.submit_url, headers=headers, json=payload)
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

            video_url = self._extract_video_url(final)
            if not video_url:
                raise RuntimeError(f"即梦任务成功但未返回视频 URL: {final}")

            video_content = await self._download_video(client, video_url)

        video_path, _ = storage.save_bytes(video_content, suffix=".mp4")
        thumbnail_path = await self._generate_thumbnail(video_path)

        # 参考价：Seedance 2.0 Mini 约 0.5 元/秒@720P（以官方 pricing 为准）
        cost = float(data.duration) * 0.5

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
                "ratio": self._resolve_ratio(data.resolution),
                "mode": "image2video" if data.image_url else "text2video",
            },
        )
