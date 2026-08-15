import asyncio
import uuid

import httpx

from app.adapters.base import VideoGenerateInput, VideoGenerateResult
from app.config import get_settings


class WanxiangVideoAdapter:
    """通义万相视频生成适配器（DashScope API）"""

    provider = "wanxiang_video"

    def __init__(self, model: str = "video-synthesis-v1") -> None:
        self.settings = get_settings()
        self.model = model

    def _build_prompt(self, data: VideoGenerateInput) -> str:
        """构建视频生成 Prompt"""
        if len(data.topic) > 100:
            return data.topic
        # 使用统一的 Prompt 模板系统
        from app.utils.prompt_templates import build_video_generation_prompt

        return build_video_generation_prompt(data)

    def _resolve_resolution(self, resolution: str) -> str:
        """解析分辨率参数"""
        resolution_map = {
            "720p": "1280*720",
            "1080p": "1920*1080",
            "portrait": "720*1280",  # 竖屏
            "square": "1024*1024",  # 方形
        }
        return resolution_map.get(resolution, "1280*720")

    async def _poll_task_status(self, client: httpx.AsyncClient, headers: dict, task_id: str) -> dict:
        """轮询任务状态直到完成或失败"""
        query_url = f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"

        for attempt in range(120):  # 最多 4 分钟（120 × 2s）
            resp = await client.get(query_url, headers=headers)
            resp.raise_for_status()
            result = resp.json()

            status = result.get("output", {}).get("task_status", "")

            if status == "SUCCEEDED":
                return result
            elif status in ("FAILED", "UNKNOWN"):
                error_msg = result.get("output", {}).get("error_message", "未知错误")
                raise RuntimeError(f"视频生成失败: {error_msg}")

            # PENDING 或 RUNNING 状态，继续等待
            await asyncio.sleep(2)

        raise TimeoutError("视频生成超时（超过 4 分钟），请稍后重试")

    async def _extract_video_url(self, result: dict) -> str:
        """从响应中提取视频 URL"""
        output = result.get("output", {})
        video_url = output.get("video_url")
        if not video_url:
            raise RuntimeError(f"未找到视频 URL: {result}")
        return video_url

    async def _generate_thumbnail(self, video_path: str) -> str:
        """生成视频首帧缩略图（使用 OpenCV）"""
        import cv2

        from app.adapters.factory import get_adapter_factory

        cap = cv2.VideoCapture(video_path)
        ret, frame = cap.read()
        cap.release()

        if not ret:
            raise RuntimeError("无法读取视频首帧")

        # 保存为 JPEG
        storage = get_adapter_factory().get_storage_adapter()
        _, thumbnail_bytes = cv2.imencode(".jpg", frame)
        thumbnail_path, _ = storage.save_bytes(thumbnail_bytes.tobytes(), suffix=".jpg")

        return thumbnail_path

    async def generate(self, data: VideoGenerateInput) -> VideoGenerateResult:
        from app.adapters.factory import get_adapter_factory
        from app.services.ai_provider_config_service import AiProviderConfigService

        prompt = self._build_prompt(data)
        storage = get_adapter_factory().get_storage_adapter()

        # 获取 API Key
        api_key = AiProviderConfigService().get_field_value("dashscope_api_key")
        if not api_key:
            # 降级到占位视频（1 秒黑屏 MP4）
            from app.adapters.ai_video.stub import StubVideoAdapter

            result = await StubVideoAdapter().generate(data)
            result.provider = self.provider
            result.prompt = prompt
            return result

        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        # 提交任务
        submit_url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2video/video-synthesis"
        resolution = self._resolve_resolution(data.resolution)

        payload = {
            "model": self.model,
            "input": {"text": prompt},
            "parameters": {
                "resolution": resolution,
                "duration": data.duration,  # 5 或 10 秒
                "fps": data.fps,
            },
        }

        # 图片转视频模式
        if data.image_url:
            payload["input"]["image_url"] = data.image_url

        async with httpx.AsyncClient(timeout=300) as client:
            # 1. 提交任务
            submit_resp = await client.post(submit_url, headers=headers, json=payload)
            submit_resp.raise_for_status()
            submit_result = submit_resp.json()

            task_id = submit_result.get("output", {}).get("task_id")
            if not task_id:
                raise RuntimeError(f"未返回 task_id: {submit_result}")

            # 2. 轮询任务状态
            final_result = await self._poll_task_status(client, headers, task_id)

            # 3. 提取视频 URL
            video_url = await self._extract_video_url(final_result)

            # 4. 下载视频到本地
            video_resp = await client.get(video_url)
            video_resp.raise_for_status()
            video_path, _ = storage.save_bytes(video_resp.content, suffix=".mp4")

        # 5. 生成缩略图
        thumbnail_path = await self._generate_thumbnail(video_path)

        # 6. 计算成本（按秒计费，假设 0.5 元/秒）
        cost = float(data.duration) * 0.5

        return VideoGenerateResult(
            video_paths=[video_path],
            thumbnail_paths=[thumbnail_path],
            provider=self.provider,
            prompt=prompt,
            cost=cost,
            duration=float(data.duration),
            metadata={"task_id": task_id, "resolution": resolution},
        )
