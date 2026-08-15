"""MiniMax (海螺) 视频生成适配器

支持四种模式:
- t2v: 文生视频 (text-to-video)
- i2v: 图生视频 (image-to-video, 照片驱动人物说话/动作)
- sef: 首尾帧视频 (start-end frame)
- ref: 主体参考视频 (subject reference)

API 文档: https://platform.minimaxi.com/document/video_generation
异步模式: 提交任务 → 轮询状态 → 下载结果
"""

import asyncio
import base64
import mimetypes
import pathlib

import httpx

from app.adapters.base import VideoGenerateInput, VideoGenerateResult


# MiniMax 视频生成 API 端点 (注意: 不是 minimax.chat, 而是 minimax.io)
API_BASE = "https://api.minimax.io/v1"
VIDEO_GENERATION_URL = f"{API_BASE}/video_generation"
QUERY_URL = f"{API_BASE}/query/video_generation"
FILE_RETRIEVE_URL = f"{API_BASE}/files/retrieve"

# 模式 → 默认模型映射
MODE_MODELS = {
    "t2v": "MiniMax-Hailuo-2.3",
    "i2v": "MiniMax-Hailuo-2.3",
    "ref": "S2V-01",
}

# 模式 → 可选模型列表
VALID_MODELS = {
    "t2v": ["MiniMax-Hailuo-2.3", "MiniMax-Hailuo-02", "MiniMax-Hailuo-01", "T2V-01", "T2V-01-Director"],
    "i2v": ["MiniMax-Hailuo-2.3", "MiniMax-Hailuo-02", "MiniMax-Hailuo-01", "I2V-01", "I2V-01-Director", "I2V-01-live"],
    "ref": ["S2V-01"],
}

POLL_INTERVAL = 10  # 秒
MAX_POLL_ATTEMPTS = 60  # 最多 600 秒


class MinimaxVideoAdapter:
    """MiniMax 海螺视频生成适配器"""

    provider = "minimax_video"

    def __init__(self, model: str = "MiniMax-Hailuo-2.3") -> None:
        self.model = model

    def _resolve_image(self, image_input: str | None) -> str | None:
        """将本地路径转为 base64 data URL, HTTP URL 直接返回"""
        if not image_input:
            return None
        if image_input.startswith(("http://", "https://", "data:")):
            return image_input
        # 本地文件 → base64
        path = pathlib.Path(image_input)
        if not path.exists():
            return image_input  # 可能是已有 URL
        mime_type, _ = mimetypes.guess_type(str(path))
        if not mime_type:
            mime_type = "image/jpeg"
        with open(path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")
        return f"data:{mime_type};base64,{encoded}"

    def _resolve_mode(self, data: VideoGenerateInput) -> str:
        """根据输入判断视频生成模式"""
        if data.avatar_type == "simulation_human":
            return "ref"  # 仿真人 → 主体参考 (S2V-01)
        if data.image_url:
            return "i2v"  # 有图片 → 图生视频
        return "t2v"  # 无图片 → 文生视频

    def _resolve_resolution(self, resolution: str) -> str:
        """分辨率映射"""
        resolution_map = {
            "720p": "1280*720",
            "1080p": "1920*1080",
            "portrait": "720*1280",
            "square": "1024*1024",
        }
        return resolution_map.get(resolution, "1280*720")

    async def _poll_task(self, task_id: str, headers: dict) -> dict:
        """轮询任务状态直到完成或失败"""
        for _ in range(MAX_POLL_ATTEMPTS):
            resp = await httpx.AsyncClient(timeout=30).get(
                QUERY_URL, headers=headers, params={"task_id": task_id}
            )
            resp.raise_for_status()
            data = resp.json()

            status = data.get("status", "Unknown")

            if status == "Success":
                return data
            if status in ("Fail", "Failed", "Error"):
                error_msg = data.get("base_resp", {}).get("status_msg", "Unknown error")
                raise RuntimeError(f"MiniMax 视频生成失败: {error_msg}")

            await asyncio.sleep(POLL_INTERVAL)

        raise TimeoutError("MiniMax 视频生成超时（超过 600 秒）")

    async def _download_video(self, file_id: str, headers: dict) -> bytes:
        """下载生成的视频文件"""
        resp = await httpx.AsyncClient(timeout=60).get(
            FILE_RETRIEVE_URL, headers=headers, params={"file_id": file_id}
        )
        resp.raise_for_status()
        return resp.content

    async def _generate_thumbnail(self, video_path: str) -> str:
        """生成视频首帧缩略图"""
        import cv2

        from app.adapters.factory import get_adapter_factory

        cap = cv2.VideoCapture(video_path)
        ret, frame = cap.read()
        cap.release()

        if not ret:
            # 如果无法读取首帧, 返回空缩略图
            storage = get_adapter_factory().get_storage_adapter()
            _, thumbnail_bytes = cv2.imencode(".jpg", frame)
            thumbnail_path, _ = storage.save_bytes(thumbnail_bytes.tobytes(), suffix=".jpg")
            return thumbnail_path

        storage = get_adapter_factory().get_storage_adapter()
        _, thumbnail_bytes = cv2.imencode(".jpg", frame)
        thumbnail_path, _ = storage.save_bytes(thumbnail_bytes.tobytes(), suffix=".jpg")
        return thumbnail_path

    async def generate(self, data: VideoGenerateInput) -> VideoGenerateResult:
        from app.adapters.factory import get_adapter_factory
        from app.services.ai_provider_config_service import AiProviderConfigService

        storage = get_adapter_factory().get_storage_adapter()
        api_key = AiProviderConfigService().get_field_value("minimax_api_key")

        if not api_key:
            from app.adapters.ai_video.stub import StubVideoAdapter

            result = await StubVideoAdapter().generate(data)
            result.provider = self.provider
            result.prompt = data.topic
            return result

        # 判断模式
        mode = self._resolve_mode(data)
        model = self.model or MODE_MODELS.get(mode, "MiniMax-Hailuo-2.3")

        # 构建请求
        headers = {"Authorization": f"Bearer {api_key}"}

        payload: dict = {
            "model": model,
            "prompt": data.topic,
            "prompt_optimizer": True,
        }

        if data.duration:
            payload["duration"] = str(data.duration)

        resolution = self._resolve_resolution(data.resolution)
        if resolution:
            payload["resolution"] = resolution

        # 图生视频模式: 添加 first_frame_image
        if mode == "i2v" and data.image_url:
            first_frame = self._resolve_image(data.image_url)
            if first_frame:
                payload["first_frame_image"] = first_frame

        # 主体参考模式 (S2V-01): 添加 subject_reference_image
        if mode == "ref" and data.image_url:
            ref_image = self._resolve_image(data.image_url)
            if ref_image:
                payload["subject_reference_image"] = ref_image

        # 提交任务
        async with httpx.AsyncClient(timeout=60) as client:
            submit_resp = await client.post(
                VIDEO_GENERATION_URL, headers=headers, json=payload
            )
            submit_resp.raise_for_status()
            submit_data = submit_resp.json()

            # 检查错误
            if "base_resp" in submit_data:
                status_code = submit_data["base_resp"].get("status_code", 0)
                if status_code != 0:
                    error_msg = submit_data["base_resp"].get("status_msg", "未知错误")
                    raise RuntimeError(f"MiniMax 视频生成提交失败: {error_msg}")

            task_id = submit_data.get("task_id")
            if not task_id:
                raise RuntimeError(f"MiniMax 未返回 task_id: {submit_data}")

        # 轮询任务 (使用独立的 client)
        final_result = await self._poll_task(task_id, headers)

        file_id = final_result.get("file_id")
        if not file_id:
            raise RuntimeError(f"MiniMax 任务成功但无 file_id: {final_result}")

        # 下载视频
        video_content = await self._download_video(file_id, headers)
        video_path, _ = storage.save_bytes(video_content, suffix=".mp4")

        # 生成缩略图
        thumbnail_path = await self._generate_thumbnail(video_path)

        # 成本估算 (MiniMax 约 0.2 元/秒)
        duration = data.duration or 5
        cost = float(duration) * 0.2

        return VideoGenerateResult(
            video_paths=[video_path],
            thumbnail_paths=[thumbnail_path],
            provider=self.provider,
            prompt=data.topic,
            cost=cost,
            duration=float(duration),
            metadata={
                "task_id": task_id,
                "mode": mode,
                "model": model,
                "resolution": resolution,
            },
        )
