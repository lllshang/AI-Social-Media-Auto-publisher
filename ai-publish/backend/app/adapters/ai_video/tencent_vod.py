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
import os
from typing import Any
from urllib.parse import urljoin

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
# 推不出 base_url 时兜底使用 uvicorn 直连端口（8000），腾讯云 VOD 走公网访问
DEFAULT_FALLBACK_PUBLIC_BASE_URL = "http://150.158.23.10:8000"


class TencentVodPermissionError(RuntimeError):
    """腾讯云 VOD AIGC 权限/开通类错误（如 Kling 数字人/对口型未开通）"""


# 权限/开通类错误码（子账号未授权、模型不支持、AIGC 未开通等）
PERMISSION_ERROR_CODES = {
    "FailedOperation.NoPermission",
    "FailedOperation.AigcNotOpen",
    "InvalidParameter.ModelNotSupported",
    "InvalidParameter.SceneTypeNotSupported",
    "InvalidParameterValue.SceneTypeNotSupported",
    "InvalidParameter.SubAppIdNotAuthorized",
    "UnauthorizedOperation",
    "AuthFailure",
}


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
        public_base_url: str | None = None,
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
        # 用于把相对路径（如 /static/materials/xxx.png）补全成外网可访问的绝对 URL，
        # 因为腾讯云 VOD 的 PullUpload 要求 MediaUrl 必须是公网可访问的绝对 URL。
        env_base = os.getenv("TENCENT_VOD_PUBLIC_BASE_URL", "").strip()
        self.public_base_url = (
            (public_base_url or env_base or DEFAULT_FALLBACK_PUBLIC_BASE_URL).rstrip("/")
        )

    def _absolutize_url(self, url: str) -> str:
        """把素材 URL 转成腾讯云可外网访问的绝对 URL。

        - 已经是 http(s):// 的直接返回
        - /static/xxx 这种容器内相对路径，用配置的 public_base_url 拼出绝对 URL
        - 如果 public_base_url 也不可用，保留原值让上层报错
        """
        if not url:
            return url
        if url.startswith(("http://", "https://")):
            return url
        if not self.public_base_url:
            return url
        if url.startswith("/"):
            return urljoin(self.public_base_url + "/", url.lstrip("/"))
        return urljoin(self.public_base_url + "/", url)

    def _get_client(self) -> vod_client.VodClient:
        """使用腾讯云官方 SDK 创建 VOD 客户端"""
        cred = credential.Credential(self.secret_id, self.secret_key)
        http_profile = HttpProfile()
        http_profile.endpoint = "vod.tencentcloudapi.com"
        client_profile = ClientProfile()
        client_profile.httpProfile = http_profile
        return vod_client.VodClient(cred, self.region, client_profile)

    _ACTION_REQUEST_CLS = {
        "CreateAigcVideoTask": models.CreateAigcVideoTaskRequest,
        "DescribeTaskDetail": models.DescribeTaskDetailRequest,
        "PullUpload": models.PullUploadRequest,
        "CreateAigcSubject": models.CreateAigcSubjectRequest,
    }
    _ACTION_SDK_METHOD = {
        "CreateAigcVideoTask": "CreateAigcVideoTask",
        "DescribeTaskDetail": "DescribeTaskDetail",
        "PullUpload": "PullUpload",
        "CreateAigcSubject": "CreateAigcSubject",
    }

    async def _call(self, client: httpx.AsyncClient, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        """调用腾讯云 VOD API（使用官方 SDK，在线程池中执行同步 SDK 调用）"""
        logger.info(f"[tencent_vod] SDK 调用开始 action={action}")
        vod_client_instance = self._get_client()

        req_cls = self._ACTION_REQUEST_CLS.get(action)
        sdk_method_name = self._ACTION_SDK_METHOD.get(action)
        if req_cls is None or sdk_method_name is None:
            raise RuntimeError(f"不支持的腾讯云 VOD API action: {action}")

        req = req_cls()
        req.from_json_string(json.dumps(payload))

        loop = asyncio.get_running_loop()
        try:
            sdk_method = getattr(vod_client_instance, sdk_method_name)
            response = await asyncio.wait_for(
                loop.run_in_executor(None, sdk_method, req),
                timeout=SDK_CALL_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.error(f"[tencent_vod] SDK 调用超时 action={action} 超时={SDK_CALL_TIMEOUT}s")
            raise RuntimeError(f"腾讯云 VOD SDK 调用超时（{SDK_CALL_TIMEOUT}s）action={action}")
        except Exception as sdk_exc:
            logger.exception(f"[tencent_vod] SDK 调用异常 action={action}", exc_info=sdk_exc)
            err_msg = str(sdk_exc)
            if any(code in err_msg for code in PERMISSION_ERROR_CODES):
                scene_hint = "数字人/对口型(Kling) " if "avatar_i2v" in err_msg or "lip" in err_msg else ""
                raise TencentVodPermissionError(
                    f"腾讯云 VOD AIGC{scene_hint}权限未开通或当前模型不支持: {err_msg}。"
                    f"请到 https://console.cloud.tencent.com/vod/aigc 开通对应能力后重试。"
                ) from sdk_exc
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

    async def _upload_url_to_vod(self, url: str, media_type: str) -> str:
        """通过 VOD PullUpload 把远程 URL 拉取到 VOD，返回 FileId。

        AIGC 接口的 FileInfos 必填 FileId（不能直接传 Url），所以需要先把
        素材 URL 上传到 VOD 拿到 FileId 再使用。
        """
        absolute_url = self._absolutize_url(url)
        if absolute_url != url:
            logger.info(f"[tencent_vod] 素材 URL 已转绝对: {url} -> {absolute_url}")
        async with httpx.AsyncClient() as client:
            resp = await self._call(client, "PullUpload", {
                "SubAppId": self.sub_app_id,
                "MediaUrl": absolute_url,
                "MediaType": media_type,
            })
            task_id = resp.get("TaskId")
            if not task_id:
                raise RuntimeError(f"腾讯云 VOD PullUpload 未返回 TaskId: {resp}")
            logger.info(f"[tencent_vod] PullUpload 已提交 TaskId={task_id}, 轮询 FileId")

            # 轮询直到拿到 FileId（PullUpload 是异步的）
            for _ in range(MAX_POLL_ATTEMPTS):
                detail = await self._call(client, "DescribeTaskDetail", {
                    "SubAppId": self.sub_app_id,
                    "TaskId": task_id,
                })
                # PullUpload 任务详情在 detail.PullUploadTask 子结构里，
                # 不是顶层 FileId / MediaBasicInfo
                task_body = detail.get("PullUploadTask") or detail
                if task_body.get("Status") == "FINISH":
                    pull_result = task_body.get("PullUploadResult") or task_body
                    file_id = (pull_result.get("FileId")
                               or task_body.get("FileId")
                               or (pull_result.get("MediaBasicInfo") or {}).get("FileId"))
                    if file_id:
                        logger.info(f"[tencent_vod] PullUpload 完成 FileId={file_id}")
                        return file_id
                    raise RuntimeError(f"腾讯云 VOD PullUpload 完成但未返回 FileId: {detail}")
                if task_body.get("Status") in ("FAILED", "FAIL"):
                    raise RuntimeError(f"腾讯云 VOD PullUpload 失败: {detail}")
                await asyncio.sleep(POLL_INTERVAL)
            raise TimeoutError(f"腾讯云 VOD PullUpload 等待 FileId 超时 url={url}")

    async def _build_file_infos_with_vod(self, data: VideoGenerateInput) -> list[dict[str, Any]] | None:
        """根据 SceneType 构造 FileInfos，并把素材 URL 转成 VOD FileId。

        - avatar_i2v（数字人）：单张参考图，Usage=Reference
        - lip_sync（对口型/仿真人）：参考视频（必）+ 可选参考音频，Usage=Reference
        - 文生/图生视频：首帧图，Usage=FirstFrame
        """
        file_infos: list[dict[str, Any]] = []

        if data.scene_type == "avatar_i2v":
            # avatar_i2v 走 Reference 图，由 SubjectInfos[Id] 引用 Kling 主体。
            # 历史测试 FileInfos=Reference + FileId 路径被腾讯云后端忽略，
            # 此处保留 FileInfo（Type=Url）以兜底万一服务端版本不同。
            if data.reference_image_url:
                url = self._absolutize_url(data.reference_image_url)
                file_infos.append({
                    "Type": "Url",
                    "Category": "Image",
                    "Url": url,
                    "Usage": "Reference",
                })
        elif data.scene_type == "lip_sync":
            if data.reference_video_url:
                file_id = await self._upload_url_to_vod(data.reference_video_url, "Video")
                file_infos.append({
                    "Type": "File",
                    "Category": "Video",
                    "FileId": file_id,
                    "Usage": "Reference",
                })
            if data.reference_audio_url:
                audio_id = await self._upload_url_to_vod(data.reference_audio_url, "Audio")
                file_infos.append({
                    "Type": "File",
                    "Category": "Audio",
                    "FileId": audio_id,
                    "Usage": "Reference",
                })
        else:
            # 文生视频 / 图生视频
            if data.image_url:
                file_id = await self._upload_url_to_vod(data.image_url, "Image")
                file_infos.append({
                    "Type": "File",
                    "Category": "Image",
                    "FileId": file_id,
                    "Usage": "FirstFrame",
                })

        return file_infos or None

    async def _register_subject(self, image_url: str, name: str) -> str:
        """调用 CreateAigcSubject 把数字人图片注册成 Kling 主体，返回 SubjectId。

        数字人（avatar_i2v）/对口型等场景需要先把人脸图注册成主体，
        再在 CreateAigcVideoTask.SubjectInfos 中传 Id 引用。
        SubjectImages 要求是公网可访问的图片 URL（直接传外链，不走 PullUpload FileId）。

        CreateAigcSubject 是异步任务：提交后只返回 TaskId，需要用 DescribeTaskDetail
        轮询 Status=FINISH，再从 CreateAigcSubjectTask.Output.SubjectId 拿到最终主体 ID。
        """
        absolute_url = self._absolutize_url(image_url)
        async with httpx.AsyncClient() as client:
            submit_resp = await self._call(client, "CreateAigcSubject", {
                "SubAppId": self.sub_app_id,
                "SubjectName": name or "avatar_subject",
                "SubjectImages": [absolute_url],
            })
            task_id = submit_resp.get("TaskId")
            if not task_id:
                raise RuntimeError(f"CreateAigcSubject 未返回 TaskId: {submit_resp}")
            logger.info(f"[tencent_vod] 主体注册已提交 TaskId={task_id}, 轮询 SubjectId")

            for _ in range(MAX_POLL_ATTEMPTS):
                detail = await self._call(client, "DescribeTaskDetail", {
                    "SubAppId": self.sub_app_id,
                    "TaskId": task_id,
                })
                # Subject 任务详情在 detail.CreateAigcSubjectTask 子结构里
                task_body = detail.get("CreateAigcSubjectTask") or detail
                status = task_body.get("Status")
                if status == "FINISH":
                    output = task_body.get("Output") or {}
                    subject_id = output.get("SubjectId")
                    if subject_id:
                        logger.info(f"[tencent_vod] 主体已注册, SubjectId={subject_id}")
                        return subject_id
                    raise RuntimeError(
                        f"CreateAigcSubject 完成但未返回 SubjectId: {detail}"
                    )
                if status in ("FAILED", "FAIL"):
                    raise RuntimeError(f"CreateAigcSubject 失败: {detail}")
                await asyncio.sleep(POLL_INTERVAL)
            raise TimeoutError(f"CreateAigcSubject 等待 SubjectId 超时 url={image_url}")

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
            err_code = task_info.get("ErrCode", 0)
            err_code_ext = task_info.get("ErrCodeExt", "")
            message = task_info.get("Message", "")

            # 腾讯云在限流等异常时也会返回 Status=FINISH，但 ErrCode != 0。
            # 必须显式检查 ErrCode，否则会把限流失败当成成功往下走。
            if status == "FINISH":
                if err_code and int(err_code) != 0:
                    err_ext = str(err_code_ext)
                    # 权限/开通类错误：明确提示用户去开通对应能力
                    if err_ext in PERMISSION_ERROR_CODES or int(err_code) == 70000 and "RequestLimitExceeded" not in err_ext:
                        scene_hint = ""
                        if "avatar_i2v" in err_ext or "lip" in err_ext:
                            scene_hint = "数字人/对口型(Kling) "
                        raise TencentVodPermissionError(
                            f"腾讯云 VOD AIGC{scene_hint}权限未开通或当前模型不支持: "
                            f"ErrCode={err_code}, ErrCodeExt={err_ext}, Message={message}。"
                            f"请到 https://console.cloud.tencent.com/vod/aigc 开通对应能力后重试。"
                        )
                    if "RequestLimitExceeded" in err_ext or int(err_code) == 70000:
                        raise RuntimeError(
                            f"腾讯云 VOD AIGC 触发限流（RequestLimitExceeded），"
                            f"请稍候再试。ErrCode={err_code}, Message={message}"
                        )
                    raise RuntimeError(
                        f"腾讯云 VOD AIGC 任务失败: ErrCode={err_code}, "
                        f"ErrCodeExt={err_code_ext}, Message={message}"
                    )
                return task_info
            if status in ("FAILED", "FAIL", "ABORTED"):
                raise RuntimeError(
                    f"腾讯云 VOD AIGC 视频生成任务失败: {task_info}"
                )

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

        # 腾讯云 VOD avatar_i2v (数字人) 测试记录：
        # 1) FileInfos+Type=File+FileId 被服务端忽略（task 后 Input.FileInfos=[]）
        # 2) SubjectInfos+Id 主体注册成功，但 avatar_i2v 仍 image 空
        # 3) FileInfos+Type=Url+Url=公网 URL 服务端能收到，但 Kling 模型仍说 image 空
        #
        # 当前采用：直接走 FileInfos+Type=Url，avatar_i2v 场景加 GenerationMode=Expert
        # 字段尝试触发 Kling 数字人专用模式（如果支持），去掉 SubjectInfos 减少干扰。
        subject_infos: list[dict[str, Any]] = []

        # 先把远程素材 URL 通过 VOD PullUpload 转成 FileId（AIGC 接口要求 FileInfos 必填 FileId）
        file_infos = await self._build_file_infos_with_vod(data)

        # 数字人/对口型/动作控制这类场景化生成必须使用 Kling 模型，
        # 覆盖工厂传入的默认模型（如 Hailuo H3），保证 SceneType 与 ModelName 一致。
        if data.scene_type in ("avatar_i2v", "lip_sync", "motion_control"):
            model_name = "Kling"
            # Kling 版本必须从 {1.6,2.0,2.1,2.5,2.6,O1,3.0,3.0-Omni} 选，
            # 不能复用 self.model_version（可能是 H3/Hailuo 等其他模型版本）。
            # 仅当 self.model_version 本身以 Kling 合法版本开头才使用，否则用 2.6。
            kling_valid_versions = {"1.6", "2.0", "2.1", "2.5", "2.6", "O1", "3.0", "3.0-Omni"}
            if self.model_version in kling_valid_versions:
                model_version = self.model_version
            else:
                model_version = "2.6"
        else:
            model_name = self.model_name
            model_version = self.model_version

        # 构建提交任务请求体
        payload: dict[str, Any] = {
            "SubAppId": self.sub_app_id,
            "ModelName": model_name,
            "ModelVersion": model_version,
        }

        # Kling 场景化生成（数字人 / 对口型 / 动作控制）
        if data.scene_type in ("avatar_i2v", "lip_sync", "motion_control"):
            payload["SceneType"] = data.scene_type

        # Prompt 优先级：场景化文本驱动 > topic
        prompt_text = data.script_text or data.topic
        if prompt_text:
            payload["Prompt"] = prompt_text

        if file_infos:
            payload["FileInfos"] = file_infos

        if subject_infos:
            payload["SubjectInfos"] = subject_infos

        # OutputConfig 控制输出行为
        output_config: dict[str, Any] = {
            "AspectRatio": self._resolve_ratio(data.resolution),
        }
        # 仿真人/数字人若已自带音频或对口型，不强制生成配音
        if data.scene_type == "lip_sync" and (data.reference_audio_url or data.reference_video_url):
            output_config["AudioGeneration"] = "Disabled"
        else:
            output_config["AudioGeneration"] = "Enabled"
        payload["OutputConfig"] = output_config

        # ExtInfo 透传额外参数，部分模型可识别 duration
        payload["ExtInfo"] = json.dumps({"duration": duration}, ensure_ascii=False)

        logger.info(
            f"[tencent_vod] 提交任务 payload: sub_app_id={self.sub_app_id}, "
            f"model={model_name}/{model_version}, scene={data.scene_type}, "
            f"ratio={self._resolve_ratio(data.resolution)}, "
            f"file_infos={file_infos}, "
            f"subject_infos={subject_infos}"
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
                "scene_type": data.scene_type,
            },
        )
