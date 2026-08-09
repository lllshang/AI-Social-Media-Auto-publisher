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
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import cv2
import httpx
import numpy as np
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
MAX_POLL_ATTEMPTS = 360  # 最多 1800 秒（30 分钟）；Kling avatar_i2v 长音频对口型官方文档可能到 20+ 分钟
SDK_CALL_TIMEOUT = 60  # 单次 SDK 同步调用超时（秒）
# 图生图参考图最长边上限（像素）。腾讯云 Hunyuan 等模型对参考图有尺寸限制，
# 超过会报 image validate failed (http_code:400)。数字人原图常是 4K 超大图，需压缩。
REFERENCE_MAX_EDGE = 1280
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
        "CreateAigcImageTask": models.CreateAigcImageTaskRequest,
        "DescribeTaskDetail": models.DescribeTaskDetailRequest,
        "PullUpload": models.PullUploadRequest,
        "CreateAigcSubject": models.CreateAigcSubjectRequest,
    }
    _ACTION_SDK_METHOD = {
        "CreateAigcVideoTask": "CreateAigcVideoTask",
        "CreateAigcImageTask": "CreateAigcImageTask",
        "DescribeTaskDetail": "DescribeTaskDetail",
        "PullUpload": "PullUpload",
        "CreateAigcSubject": "CreateAigcSubject",
    }

    async def _call(self, client: httpx.AsyncClient, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        """调用腾讯云 VOD API（使用官方 SDK，在线程池中执行同步 SDK 调用）"""
        logger.info(f"[tencent_vod] SDK 调用开始 action={action}")
        # SubAppId 在配置里是字符串，但腾讯云 SDK 要求 uint64，否则报
        # "参数 SubAppId 取值类型错误。参数类型应为 uint64"（CreateAigcImageTask 尤其严格）
        if "SubAppId" in payload and payload["SubAppId"] not in (None, ""):
            try:
                payload = {**payload, "SubAppId": int(payload["SubAppId"])}
            except (TypeError, ValueError):
                pass
        # 诊断：把发出的完整 payload 落盘，确认 ExtInfo.sound_file 等字段是否拼对
        if action == "CreateAigcVideoTask":
            try:
                dump_path = Path("/data/materials/last_payload.json")
                dump_path.parent.mkdir(parents=True, exist_ok=True)
                dump_path.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                logger.info(f"[tencent_vod][DUMP] CreateAigcVideoTask payload 已落盘: {dump_path}")
            except Exception as _dump_err:
                logger.warning(f"[tencent_vod][DUMP] 落盘失败: {_dump_err}")
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
            # 腾讯云 VOD 官方文档（Kling 数字人 avatar_i2v = 对口型）：
            # 1) 图片通过 FileInfos 指定，Category="Image"，无需 Usage 字段
            # 2) 音频必须在 ExtInfo.AdditionalParameters.sound_file 中指定（URL 或 Base64）
            #    sound_file 支持 mp3/wav/m4a/aac，≤5MB，2~300秒
            # 注意：实测 FileInfos 里加 Category=Audio 会被腾讯云拒（ErrCode:InternalError
            # image must not be blank），所以音频**只能**走 ExtInfo 通道。
            if data.reference_image_url:
                # 数字人参考图：保持传 Url（与 id=70 成功链路一致）
                # 此处不要走 _upload_url_to_vod 转 FileId，Kling avatar_i2v
                # 场景下直接传 Url 才能成功（FileId 会被拒：image must not be blank）
                url = self._absolutize_url(data.reference_image_url)
                file_infos.append({
                    "Type": "Url",
                    "Category": "Image",
                    "Url": url,
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
            # 注意：音频**不能**走 FileInfos（实测会被腾讯云拒：
            # ErrCode:InternalError image must not be blank），
            # 必须统一通过 ExtInfo.AdditionalParameters.sound_file 传入
            # （见下方 avatar_i2v/lip_sync 的 ExtInfo 分支）。这里不要加 Category=Audio。
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

        # 数字人 avatar_i2v 主体注册（Kling SubjectInfos）：
        # 把「干净的数字人原图」注册成主体，让 Kling 只驱动人脸区域，
        # 背景（background_image_url 里的书架/杂物）保持不动，彻底解决
        # 「主体漂移 / 背景重绘出小人、镜像文字」问题。
        #
        # 注册图用 subject_image_url（即 Avatar.reference_image_url，单人原图，无杂物），
        # 与视频驱动图 reference_image_url（带背景图）解耦——两者用不同图。
        # 若上游已缓存 avatar_subject_id 则直接复用，跳过创建。
        subject_infos: list[dict[str, Any]] = []
        new_subject_id: str | None = None
        if data.scene_type == "avatar_i2v" and (data.avatar_subject_id or data.subject_image_url):
            if data.avatar_subject_id:
                logger.info(f"[tencent_vod] 复用已缓存主体 SubjectId={data.avatar_subject_id}")
                subject_infos = [{"Id": data.avatar_subject_id, "Usage": "Main"}]
            elif data.subject_image_url:
                registered = await self._register_subject(data.subject_image_url, "avatar_subject")
                new_subject_id = registered
                subject_infos = [{"Id": registered, "Usage": "Main"}]

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
                # 默认 2.6（id=70 成功链路用的就是 2.6）
                # 之前曾临时改 2.0 想绕开硬字幕，但实测 2.0 同样会加中间乱码字幕，
                # 真正决定是否加字幕的是 prompt 长度/音频时长，不在此处理。
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
        # 计算数字人场景是否有音频源：material_service 已经在
        # TTS 合成阶段把数据写入 reference_audio_url；若仍为空才退到占位
        # 静音（极少走此分支，作为链路兜底）。
        has_audio_source = bool(
            data.reference_audio_url or data.reference_video_url
        )
        if data.scene_type in ("avatar_i2v", "lip_sync") and has_audio_source:
            output_config["AudioGeneration"] = "Disabled"
        else:
            output_config["AudioGeneration"] = "Enabled"
        payload["OutputConfig"] = output_config

        # ExtInfo 透传额外参数（腾讯云 VOD AIGC 通用机制）
        # 官方文档：数字人 avatar_i2v 的音频必须提供（audio_id 或 sound_file 二选一），
        # 通过 ExtInfo.AdditionalParameters.sound_file 指定（URL 或 Base64）。
        # 音频源：material_service 提前用 edge-tts 合成了真实口播 mp3
        # （并写入 reference_audio_url），所以这里一定能拿到音频 URL。
        #
        # 注意：ExtInfo.duration 是无效字段（Kling 数字人时长由音频驱动），
        # 不再下发表面的 duration，避免误导。时长由 sound_file 音频真实长度决定。
        ext_info: dict[str, Any] = {}
        # avatar_i2v 与 lip_sync(仿真人) 都需要把 TTS 合成的口播音频作为 sound_file
        # 传入，否则 Kling 会沿用参考视频原音轨，导致「口播词」完全不生效。
        if data.scene_type in ("avatar_i2v", "lip_sync"):
            audio_url = data.reference_audio_url
            if not audio_url:
                # 兜底：占位静音 wav
                audio_url = os.getenv(
                    "TENCENT_VOD_PLACEHOLDER_AUDIO_URL",
                    f"{self.public_base_url}/static/materials/placeholder_silence.wav",
                )
            if audio_url:
                additional = json.dumps(
                    {"sound_file": self._absolutize_url(audio_url)},
                    ensure_ascii=False,
                )
                ext_info["AdditionalParameters"] = additional
        if ext_info:
            payload["ExtInfo"] = json.dumps(ext_info, ensure_ascii=False)

        # 诊断：在拼完 payload 的瞬间落盘（不依赖 action 名匹配，确保任何一次提交都能抓到）
        try:
            dump_path = Path("/data/materials/last_payload.json")
            dump_path.parent.mkdir(parents=True, exist_ok=True)
            dump_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            logger.info(f"[tencent_vod][DUMP] submit payload 已落盘: {dump_path}")
        except Exception as _dump_err:
            logger.warning(f"[tencent_vod][DUMP] 落盘失败: {_dump_err}")

        logger.info(
            f"[tencent_vod] 提交任务 payload: sub_app_id={self.sub_app_id}, "
            f"model={model_name}/{model_version}, scene={data.scene_type}, "
            f"ratio={self._resolve_ratio(data.resolution)}, "
            f"file_infos={file_infos}, "
            f"subject_infos={subject_infos}"
        )
        # 诊断：明确打印音频源，确认 sound_file 是否进入 ExtInfo
        logger.info(
            f"[tencent_vod][DIAG] reference_audio_url={data.reference_audio_url!r}, "
            f"audio_duration={data.audio_duration!r}, has_audio_source={has_audio_source}, "
            f"file_infos={file_infos!r}, "
            f"ExtInfo={payload.get('ExtInfo')!r}, "
            f"AudioGeneration={output_config.get('AudioGeneration')!r}"
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

        # 数字人/对口型视频时长 = 喂给 Kling 的音频时长（ExtInfo.duration 无效）。
        # 优先用 material_service 合成的真实音频时长（挂到 data.duration）；
        # 若拿不到则回退到前端传入的 duration，最终兜底探测下载视频真实时长。
        actual_duration = float(duration)
        if data.audio_duration and data.audio_duration > 0:
            actual_duration = float(data.audio_duration)
        else:
            try:
                import cv2
                cap = cv2.VideoCapture(video_path)
                fps = cap.get(cv2.CAP_PROP_FPS) or 0
                frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
                if fps and frames:
                    actual_duration = frames / fps
                cap.release()
            except Exception:
                pass

        cost = actual_duration * self.cost_per_second
        elapsed = time.time() - start_time

        return VideoGenerateResult(
            video_paths=[video_path],
            thumbnail_paths=[thumbnail_path],
            provider=self.provider,
            prompt=data.topic,
            cost=cost,
            duration=actual_duration,
            elapsed=elapsed,
            metadata={
                "task_id": task_id,
                "model_name": self.model_name,
                "model_version": self.model_version,
                "sub_app_id": self.sub_app_id,
                "ratio": self._resolve_ratio(data.resolution),
                "mode": "image2video" if data.image_url else "text2video",
                "scene_type": data.scene_type,
                "subject_id": new_subject_id,
            },
        )

    async def _prepare_reference_image(self, reference_url: str, client: httpx.AsyncClient) -> str:
        """下载参考图并按腾讯云要求压缩，返回可外网访问的绝对 URL。

        腾讯云 VOD 的 Hunyuan 等图生图模型对参考图有尺寸/文件大小上限，
        过大的原图（如 3840x5760 / 11MB 的数字人原图）会直接报
        ``image validate failed (http_code:400)``。因此这里统一把参考图
        下载下来，最长边缩放到 <= ``REFERENCE_MAX_EDGE``，再落盘到素材目录，
        返回拼好的公网 URL 供 PullUpload 使用。

        若图片本身已符合限制，也会重新落地一次（幂等，仅多一次落盘开销）。
        """
        from app.adapters.factory import get_adapter_factory

        resp = await client.get(reference_url, timeout=120)
        resp.raise_for_status()
        raw = resp.content

        img = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            # 解码失败（非图片/损坏），原样返回让上层 PullUpload 报错，保留原始信息
            logger.warning("[tencent_vod] 参考图解码失败，跳过压缩: %s", reference_url)
            return reference_url

        h, w = img.shape[:2]
        max_edge = REFERENCE_MAX_EDGE
        long_edge = max(h, w)
        if long_edge > max_edge:
            scale = max_edge / float(long_edge)
            new_size = (int(round(w * scale)), int(round(h * scale)))
            img = cv2.resize(img, new_size, interpolation=cv2.INTER_AREA)
            logger.info("[tencent_vod] 参考图已缩放 %dx%d -> %dx%d", w, h, new_size[0], new_size[1])

        ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ok:
            logger.warning("[tencent_vod] 参考图编码失败，跳过压缩: %s", reference_url)
            return reference_url
        compressed = buf.tobytes()

        storage = get_adapter_factory().get_storage_adapter()
        _abs_path, rel_url = storage.save_bytes(compressed, suffix=".jpg")
        public_url = self._absolutize_url(rel_url)
        logger.info("[tencent_vod] 参考图压缩后落盘: %s (%d bytes)", public_url, len(compressed))
        return public_url

    async def generate_image(self, data: "ImageGenerateInput") -> "ImageGenerateResult":
        """腾讯云 VOD AIGC 图生图 / 文生图。

        用于「数字人背景生成」：把用户上传的数字人原图（reference_image_url）
        作为参考图，配合背景描述（background_prompt / topic）生成带背景的数字人图。

        - 图生图：ModelName=Hunyuan, ModelVersion=3.0 + FileInfos 参考图（Usage=Reference）
        - 文生图：不传参考图，纯 Prompt 驱动
        - 返回 count 张图（单次任务出 1 张，循环提交 count 次）
        """
        from app.adapters.base import ImageGenerateInput, ImageGenerateResult
        from app.adapters.factory import get_adapter_factory

        if not self.secret_id or not self.secret_key:
            raise RuntimeError("腾讯云 VOD AIGC 适配器缺少 SecretId/SecretKey 配置")
        if not self.sub_app_id:
            raise RuntimeError("腾讯云 VOD AIGC 适配器缺少 SubAppId 配置")

        import time
        start_time = time.time()

        # 图生图固定用 Hunyuan 3.0（中文提示词理解最好，支持参考图）
        model_name = "Hunyuan"
        model_version = "3.0"

        # 背景描述优先 background_prompt，其次 topic
        prompt_text = (getattr(data, "background_prompt", None)
                       or getattr(data, "topic", None)
                       or "")
        if not prompt_text:
            raise RuntimeError("图生图缺少背景描述（background_prompt / topic）")

        reference_url = getattr(data, "reference_image_url", None)
        # 若调用方传入容器内相对路径（如 /static/materials/xxx），补成公网 URL，
        # 否则 _prepare_reference_image / PullUpload 都拿不到图。
        if reference_url and reference_url.startswith("/"):
            reference_url = self._absolutize_url(reference_url)
        is_image2image = bool(reference_url)

        # 构造参考图 FileInfos（图生图需要）
        # 注意：参考图必须先压缩（超大原图腾讯云会 image validate failed 400）
        # 再 PullUpload 到腾讯云 VOD 拿到 FileId 用 Type=File+FileId 传，
        # 不能直接传公网 Url（腾讯云侧拉取公网 URL 经常因安全组/白名单失败）。
        file_infos: list[dict[str, Any]] | None = None
        if is_image2image:
            async with httpx.AsyncClient() as client:
                # 1) 下载并压缩参考图（最长边 <= REFERENCE_MAX_EDGE），返回公网可访问 URL
                prepared_url = await self._prepare_reference_image(reference_url, client)
                # 2) 压缩后的图 PullUpload 到 VOD 拿 FileId
                ref_file_id = await self._upload_url_to_vod(prepared_url, "Image")
            file_infos = [{
                "Type": "File",
                "Category": "Image",
                "FileId": ref_file_id,
                "Usage": "Reference",
            }]

        count = max(1, int(getattr(data, "count", 1) or 1))
        image_paths: list[str] = []
        storage = get_adapter_factory().get_storage_adapter()

        async with httpx.AsyncClient() as client:
            for idx in range(count):
                payload: dict[str, Any] = {
                    "SubAppId": self.sub_app_id,
                    "ModelName": model_name,
                    "ModelVersion": model_version,
                    "Prompt": prompt_text,
                }
                if file_infos:
                    payload["FileInfos"] = file_infos
                # 图生图时关闭文生图自带的音频生成（图片任务不需要）
                payload["OutputConfig"] = {"AspectRatio": self._resolve_ratio(
                    getattr(data, "ratio", "3:4") or "3:4")}

                try:
                    resp = await self._call(client, "CreateAigcImageTask", payload)
                except Exception as exc:
                    logger.exception(f"[tencent_vod] 创建 AIGC 图片任务失败: {exc}")
                    raise

                task_id = resp.get("TaskId")
                if not task_id:
                    raise RuntimeError(f"腾讯云 VOD AIGC 图片任务未返回 TaskId: {resp}")

                # 轮询图片任务（结构类似视频，但子对象是 AigcImageTask）
                image_url = await self._poll_image_task(client, task_id)
                logger.info(f"[tencent_vod] 图片任务 {idx + 1}/{count} 完成, url={image_url[:80]}")

                img_bytes = await self._download_image(client, image_url)
                saved_path, _ = storage.save_bytes(img_bytes, suffix=".jpg")
                image_paths.append(saved_path)

        elapsed = time.time() - start_time
        return ImageGenerateResult(
            image_paths=image_paths,
            provider=self.provider,
            prompt=prompt_text,
            elapsed=elapsed,
        )

    async def _poll_image_task(self, client: httpx.AsyncClient, task_id: str) -> str:
        """轮询图片 AIGC 任务，返回生成图片的公网 URL。"""
        for attempt in range(MAX_POLL_ATTEMPTS):
            resp = await self._call(
                client,
                "DescribeTaskDetail",
                {
                    "SubAppId": self.sub_app_id,
                    "TaskId": task_id,
                },
            )
            task_info = resp.get("AigcImageTask", {})
            status = task_info.get("Status", "")
            err_code = task_info.get("ErrCode", 0)
            err_code_ext = task_info.get("ErrCodeExt", "")
            message = task_info.get("Message", "")

            if status == "FINISH":
                if err_code and int(err_code) != 0:
                    err_ext = str(err_code_ext)
                    if err_ext in PERMISSION_ERROR_CODES:
                        raise TencentVodPermissionError(
                            f"腾讯云 VOD AIGC 图片生成权限未开通: "
                            f"ErrCode={err_code}, ErrCodeExt={err_ext}, Message={message}。"
                            f"请到 https://console.cloud.tencent.com/vod/aigc 开通对应能力后重试。"
                        )
                    raise RuntimeError(
                        f"腾讯云 VOD AIGC 图片生成任务失败: "
                        f"ErrCode={err_code}, ErrCodeExt={err_code_ext}, Message={message}"
                    )
                output = task_info.get("Output", {})
                image_url = output.get("Url") or output.get("MediaUrl")
                if not image_url:
                    file_infos = output.get("FileInfos") or []
                    for file_info in file_infos:
                        image_url = image_url or file_info.get("FileUrl")
                        if image_url:
                            break
                if not image_url:
                    raise RuntimeError(f"腾讯云 VOD AIGC 图片任务成功但未返回 URL: {task_info}")
                return image_url
            if status in ("FAILED", "FAIL", "ABORTED"):
                raise RuntimeError(f"腾讯云 VOD AIGC 图片生成任务失败: {task_info}")
            await asyncio.sleep(POLL_INTERVAL)
        raise TimeoutError("腾讯云 VOD AIGC 图片生成超时")

    async def _download_image(self, client: httpx.AsyncClient, image_url: str) -> bytes:
        resp = await client.get(image_url, timeout=120)
        resp.raise_for_status()
        return resp.content
