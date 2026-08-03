"""腾讯云点播 VOD AIGC 视频生成适配器

对接腾讯云点播 VOD 的「创建 AIGC 生视频任务」接口：
- 提交任务 Action=CreateAigcVideoTask
- 查询任务 Action=DescribeTaskDetail
- 签名方式：腾讯云 API 3.0 TC3-HMAC-SHA256

官方文档：
- https://cloud.tencent.com/document/product/266/126239
- https://cloud.tencent.com/document/product/266/33431

该接口是一个统一网关，底层可接入多个第三方模型：
Kling / Vidu / Hailuo / Hunyuan / Mingmou / GV / OS / PixVerse
"""

import asyncio
import datetime as dt
import json
from typing import Any

import cv2
import httpx
import numpy as np
from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.vod.v20180717 import vod_client, models

from app.adapters.base import VideoGenerateInput, VideoGenerateResult
from app.adapters.factory import get_adapter_factory

import logging

logger = logging.getLogger(__name__)


DEFAULT_BASE_URL = "https://vod.tencentcloudapi.com"
DEFAULT_REGION = "ap-guangzhou"
DEFAULT_VERSION = "2018-07-17"
POLL_INTERVAL = 5
MAX_POLL_ATTEMPTS = 120
SDK_CALL_TIMEOUT = 60  # 单次 SDK 同步调用超时（秒）


class TencentVodVideoAdapter:
    """腾讯云点播 VOD AIGC 视频生成适配器"""

    provider = "tencent_vod_video"

    def __init__(
        self,
        model_name: str = "Hunyuan",
        model_version: str = "1.5",
        sub_app_id: str | int | None = None,
        secret_id: str | None = None,
        secret_key: str | None = None,
        region: str = DEFAULT_REGION,
        base_url: str = DEFAULT_BASE_URL,
        cost_per_second: float = 0.0,
    ) -> None:
        self.model_name = model_name
        self.model_version = model_version
        self.sub_app_id = int(sub_app_id) if sub_app_id else 0
        self.secret_id = secret_id or ""
        self.secret_key = secret_key or ""
        self.region = region
        self.base_url = base_url.rstrip("/")
        try:
            self.cost_per_second = float(cost_per_second)
        except (TypeError, ValueError):
            self.cost_per_second = 0.0

    def _get_client(self) -> vod_client.VodClient:
        """使用腾讯云官方 SDK 创建 VOD 客户端"""
        cred = credential.Credential(self.secret_id, self.secret_key)
        http_profile = HttpProfile()
        http_profile.endpoint = "vod.tencentcloudapi.com"
        client_profile = ClientProfile()
        client_profile.httpProfile = http_profile
        return vod_client.VodClient(cred, self.region, client_profile)

    async def _call(self, client: httpx.AsyncClient, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        """调用腾讯云 VOD API（使用官方 SDK，在线程池中执行同步 SDK 调用）"""
        logger.info(f"[tencent_vod] SDK 调用开始 action={action}")
        vod_client_instance = self._get_client()

        if action == "CreateAigcVideoTask":
            req = models.CreateAigcVideoTaskRequest()
            params = payload
        elif action == "DescribeTaskDetail":
            req = models.DescribeTaskDetailRequest()
            params = payload
        else:
            raise RuntimeError(f"不支持的腾讯云 VOD API action: {action}")

        req.from_json_string(json.dumps(params))

        loop = asyncio.get_running_loop()
        try:
            if action == "CreateAigcVideoTask":
                response = await asyncio.wait_for(
                    loop.run_in_executor(None, vod_client_instance.CreateAigcVideoTask, req),
                    timeout=SDK_CALL_TIMEOUT,
                )
            else:
                response = await asyncio.wait_for(
                    loop.run_in_executor(None, vod_client_instance.DescribeTaskDetail, req),
                    timeout=SDK_CALL_TIMEOUT,
                )
        except asyncio.TimeoutError:
            logger.error(f"[tencent_vod] SDK 调用超时 action={action} 超时={SDK_CALL_TIMEOUT}s")
            raise RuntimeError(f"腾讯云 VOD SDK 调用超时（{SDK_CALL_TIMEOUT}s）action={action}")
        except Exception as sdk_exc:
            logger.exception(f"[tencent_vod] SDK 调用异常 action={action}", exc_info=sdk_exc)
            raise

        result = json.loads(response.to_json_string())
        logger.info(f"[tencent_vod] SDK 调用完成 action={action}")
        return result

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

    def _resolve_duration(self, duration: float | int | None) -> int:
        try:
            return max(1, int(duration or 5))
        except (TypeError, ValueError):
            return 5

    def _build_file_infos(self, image_url: str | None) -> list[dict[str, Any]] | None:
        if not image_url:
            return None
        return [
            {
                "Usage": "FirstFrame",
                "Url": image_url,
            }
        ]

    async def _generate_thumbnail(self, video_path: str) -> str:
        from app.adapters.factory import get_adapter_factory

        storage = get_adapter_factory().get_storage_adapter()
        cap = cv2.VideoCapture(video_path)
        ret, frame = cap.read()
        cap.release()

        if not ret:
            black = np.zeros((720, 1280, 3), dtype=np.uint8)
            _, thumbnail_bytes = cv2.imencode(".jpg", black)
        else:
            _, thumbnail_bytes = cv2.imencode(".jpg", frame)

        thumbnail_path, _ = storage.save_bytes(thumbnail_bytes.tobytes(), suffix=".jpg")
        return thumbnail_path

    async def _download_video(self, client: httpx.AsyncClient, video_url: str) -> bytes:
        resp = await client.get(video_url, timeout=120)
        resp.raise_for_status()
        return resp.content

    async def _poll_task(self, client: httpx.AsyncClient, task_id: str) -> dict[str, Any]:
        for attempt in range(MAX_POLL_ATTEMPTS):
            resp = await self._call(
                client,
                "DescribeTaskDetail",
                {
                    "SubAppId": self.sub_app_id,
                    "TaskId": task_id,
                },
            )
            task_info = resp.get("AigcVideoTask", {})
            status = task_info.get("Status", "")

            if status == "FINISH":
                return task_info
            if status in ("FAILED", "FAIL", "ABORTED"):
                raise RuntimeError(f"腾讯云 VOD AIGC 视频生成任务失败: {task_info}")

            await asyncio.sleep(POLL_INTERVAL)

        raise TimeoutError("腾讯云 VOD AIGC 视频生成超时（超过 600 秒）")

    async def generate(self, data: VideoGenerateInput) -> VideoGenerateResult:
        if not self.secret_id or not self.secret_key:
            raise RuntimeError("腾讯云 VOD AIGC 适配器缺少 SecretId/SecretKey 配置")
        if not self.sub_app_id:
            raise RuntimeError("腾讯云 VOD AIGC 适配器缺少 SubAppId 配置")

        import time

        start_time = time.time()
        duration = self._resolve_duration(data.duration)
        file_infos = self._build_file_infos(data.image_url)

        # 构建提交任务请求体
        payload: dict[str, Any] = {
            "SubAppId": self.sub_app_id,
            "ModelName": self.model_name,
            "ModelVersion": self.model_version,
        }

        if data.topic:
            payload["Prompt"] = data.topic

        if file_infos:
            payload["FileInfos"] = file_infos

        # OutputConfig 控制输出行为
        payload["OutputConfig"] = {
            "AspectRatio": self._resolve_ratio(data.resolution),
            "AudioGeneration": "Enabled",
        }

        # ExtInfo 透传额外参数，部分模型可识别 duration
        payload["ExtInfo"] = json.dumps({"duration": duration}, ensure_ascii=False)

        logger.info(
            f"[tencent_vod] 提交任务 payload: sub_app_id={self.sub_app_id}, "
            f"model={self.model_name}/{self.model_version}, ratio={self._resolve_ratio(data.resolution)}"
        )
        async with httpx.AsyncClient() as client:
            try:
                resp = await self._call(client, "CreateAigcVideoTask", payload)
            except Exception as exc:
                logger.exception(f"[tencent_vod] 创建 AIGC 任务失败: {exc}")
                raise
            task_id = resp.get("TaskId")
            if not task_id:
                logger.error(f"[tencent_vod] 未返回 TaskId, resp={resp}")
                raise RuntimeError(f"腾讯云 VOD AIGC 未返回 TaskId: {resp}")
            logger.info(f"[tencent_vod] 任务已提交, TaskId={task_id}, 开始轮询")

            task_info = await self._poll_task(client, task_id)
            logger.info(f"[tencent_vod] 任务完成, task_info={task_info}")

            output = task_info.get("Output", {})
            video_url = output.get("Url") or output.get("MediaUrl")
            if not video_url:
                file_infos = output.get("FileInfos") or []
                for file_info in file_infos:
                    video_url = video_url or file_info.get("FileUrl")
                    if video_url:
                        break
            if not video_url:
                logger.error(f"[tencent_vod] 任务成功但未返回视频 URL: {task_info}")
                raise RuntimeError(f"腾讯云 VOD AIGC 任务成功但未返回视频 URL: {task_info}")

            logger.info(f"[tencent_vod] 开始下载视频 url={video_url[:80]}")
            video_content = await self._download_video(client, video_url)
            logger.info(f"[tencent_vod] 视频下载完成 bytes={len(video_content)}")

        storage = get_adapter_factory().get_storage_adapter()
        video_path, _ = storage.save_bytes(video_content, suffix=".mp4")
        thumbnail_path = await self._generate_thumbnail(video_path)

        cost = float(duration) * self.cost_per_second
        elapsed = time.time() - start_time

        return VideoGenerateResult(
            video_paths=[video_path],
            thumbnail_paths=[thumbnail_path],
            provider=self.provider,
            prompt=data.topic,
            cost=cost,
            duration=float(duration),
            elapsed=elapsed,
            metadata={
                "task_id": task_id,
                "model_name": self.model_name,
                "model_version": self.model_version,
                "sub_app_id": self.sub_app_id,
                "ratio": self._resolve_ratio(data.resolution),
                "mode": "image2video" if data.image_url else "text2video",
            },
        )
