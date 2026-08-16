"""腾讯云点播 VOD AIGC 生图适配器。

使用腾讯云官方 SDK 调用 VOD 的 AIGC 图像生成能力。
开通与密钥同视频生成（SubAppId + SecretId/SecretKey）。
"""

import asyncio
import json
import time
from typing import Any

import httpx

from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.vod.v20180717 import vod_client, models

from app.adapters.base import ImageGenerateInput, ImageGenerateResult
from app.adapters.factory import get_adapter_factory


DEFAULT_REGION = "ap-guangzhou"
POLL_INTERVAL = 3
MAX_POLL_ATTEMPTS = 120


class TencentVodImageAdapter:
    """腾讯云点播 VOD AIGC 图像生成适配器"""

    provider = "tencent_vod_image"

    def __init__(
        self,
        model_name: str = "Hunyuan",
        model_version: str = "3.0",
        sub_app_id: str | int | None = None,
        secret_id: str | None = None,
        secret_key: str | None = None,
        region: str = DEFAULT_REGION,
        cost_per_image: float = 0.0,
    ) -> None:
        self.model_name = model_name
        self.model_version = model_version
        self.sub_app_id = int(sub_app_id) if sub_app_id else 0
        self.secret_id = secret_id or ""
        self.secret_key = secret_key or ""
        self.region = region
        try:
            self.cost_per_image = float(cost_per_image)
        except (TypeError, ValueError):
            self.cost_per_image = 0.0

    def _get_client(self) -> vod_client.VodClient:
        cred = credential.Credential(self.secret_id, self.secret_key)
        http_profile = HttpProfile()
        http_profile.endpoint = "vod.tencentcloudapi.com"
        client_profile = ClientProfile()
        client_profile.httpProfile = http_profile
        return vod_client.VodClient(cred, self.region, client_profile)

    async def _call(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        vod_client_instance = self._get_client()

        if action == "CreateAigcImageTask":
            req = models.CreateAigcImageTaskRequest()
        elif action == "DescribeTaskDetail":
            req = models.DescribeTaskDetailRequest()
        else:
            raise RuntimeError(f"不支持的腾讯云 VOD API action: {action}")

        req.from_json_string(json.dumps(payload))

        loop = asyncio.get_running_loop()
        if action == "CreateAigcImageTask":
            response = await loop.run_in_executor(None, vod_client_instance.CreateAigcImageTask, req)
        else:
            response = await loop.run_in_executor(None, vod_client_instance.DescribeTaskDetail, req)

        return json.loads(response.to_json_string())

    def _resolve_ratio(self, ratio: str) -> str:
        r = (ratio or "").lower()
        if "3:4" in r:
            return "3:4"
        if "9:16" in r or "竖" in r or "portrait" in r:
            return "9:16"
        if "1:1" in r or "square" in r:
            return "1:1"
        if "16:9" in r or "横" in r or "landscape" in r:
            return "16:9"
        return "3:4"

    async def _download_image(self, client: httpx.AsyncClient, image_url: str) -> bytes:
        resp = await client.get(image_url, timeout=120)
        resp.raise_for_status()
        return resp.content

    async def _poll_task(self, task_id: str) -> dict[str, Any]:
        for _ in range(MAX_POLL_ATTEMPTS):
            resp = await self._call(
                "DescribeTaskDetail",
                {
                    "SubAppId": self.sub_app_id,
                    "TaskId": task_id,
                },
            )
            task_info = resp.get("AigcImageTask", {}) or resp.get("AigcImageTaskSet", [{}])
            if isinstance(task_info, list):
                task_info = task_info[0] if task_info else {}
            status = task_info.get("Status", "")

            if status == "FINISH":
                return task_info
            if status in ("FAILED", "FAIL", "ABORTED"):
                raise RuntimeError(f"腾讯云 VOD AIGC 图像生成任务失败: {task_info}")

            await asyncio.sleep(POLL_INTERVAL)

        raise TimeoutError("腾讯云 VOD AIGC 图像生成超时（超过 360 秒）")

    async def generate(self, data: ImageGenerateInput) -> ImageGenerateResult:
        if not self.secret_id or not self.secret_key:
            raise RuntimeError("腾讯云 VOD AIGC 生图适配器缺少 SecretId/SecretKey 配置")
        if not self.sub_app_id:
            raise RuntimeError("腾讯云 VOD AIGC 生图适配器缺少 SubAppId 配置")

        start_time = time.time()
        count = max(1, int(data.count or 1))

        payload: dict[str, Any] = {
            "SubAppId": self.sub_app_id,
            "ModelName": self.model_name,
            "ModelVersion": self.model_version,
            "Prompt": data.topic,
            "Amount": count,
            "OutputConfig": {
                "AspectRatio": self._resolve_ratio(data.ratio),
            },
        }
        if data.style and data.style != "default":
            payload["Style"] = data.style

        async with httpx.AsyncClient() as client:
            resp = await self._call("CreateAigcImageTask", payload)
            task_id = resp.get("TaskId")
            if not task_id:
                raise RuntimeError(f"腾讯云 VOD AIGC 生图未返回 TaskId: {resp}")

            task_info = await self._poll_task(task_id)

            output = task_info.get("Output", {})
            image_urls = output.get("ImageUrls") or output.get("Urls") or []
            if not image_urls:
                image_url = output.get("Url") or output.get("ImageUrl")
                if image_url:
                    image_urls = [image_url]

            if not image_urls:
                file_infos = output.get("FileInfos") or []
                for file_info in file_infos:
                    url = file_info.get("FileUrl") or file_info.get("Url")
                    if url:
                        image_urls.append(url)

            if not image_urls:
                raise RuntimeError(f"腾讯云 VOD AIGC 图像生成成功但未返回图片 URL: {task_info}")

            image_paths: list[str] = []
            storage = get_adapter_factory().get_storage_adapter()
            for image_url in image_urls:
                image_content = await self._download_image(client, image_url)
                image_path, _ = storage.save_bytes(image_content, suffix=".png")
                image_paths.append(image_path)

        elapsed = time.time() - start_time
        cost = float(count) * self.cost_per_image

        return ImageGenerateResult(
            image_paths=image_paths,
            provider=self.provider,
            prompt=data.topic,
            cost=cost,
            elapsed=elapsed,
            negative_prompt=None,
        )
