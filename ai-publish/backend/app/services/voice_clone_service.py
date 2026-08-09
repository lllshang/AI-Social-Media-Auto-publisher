"""
腾讯云「声音复刻」（VRS, Voice Replica Service）服务

完整链路：
  1. 用户上传一段清晰中文录音（建议 10s 左右，单人、无背景音）
  2. DetectEnvAndSoundQuality  -> 拿 AudioId（一句话复刻 TaskType=5）
  3. CreateVRSTask             -> 拿 TaskId
  4. DescribeVRSTaskStatus 轮询 -> 训练成功拿 VoiceType（整数音色 ID）
  5. 之后用 VoiceType 走现有 TTS TextToVoice 合成任意口播文本

说明：
  - VRS 是独立产品（vrs.tencentcloudapi.com），与 TTS 共用同一套腾讯云密钥。
  - 复刻出来的 VoiceType 是「整数」，可直接喂给 tts.py 的 _synthesize_one(voice_type=int)。
  - 训练是异步的，通常需要几分钟。前端可定时轮询 status 接口。
"""

from __future__ import annotations

import base64
import json
import logging
import os
import uuid
from typing import Optional

logger = logging.getLogger(__name__)

from tencentcloud.common import credential
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
from tencentcloud.vrs.v20200824 import vrs_client, models

from app.services.ai_provider_config_service import AiProviderConfigService
from app.models import VoiceCloneTask
from app.database import SessionLocal


# 一句话复刻：只需一段音频
VRS_TASK_TYPE_ONESHOT = 5
# 音频类型（TypeId）：1-常规
VRS_TYPE_ID_NORMAL = 1
# 语言：1-中文
VRS_LANG_ZH = 1


def _get_vrs_client() -> vrs_client.VrsClient:
    cfg = AiProviderConfigService()
    secret_id = cfg.get_field_value("tencent_vod_secret_id") or ""
    secret_key = cfg.get_field_value("tencent_vod_secret_key") or ""
    if not secret_id or not secret_key:
        raise RuntimeError("缺少腾讯云密钥（tencent_vod_secret_id / tencent_vod_secret_key）")
    cred = credential.Credential(secret_id, secret_key)
    return vrs_client.VrsClient(cred, "ap-guangzhou")


def _read_audio_as_b64(audio_path: str) -> tuple[str, str]:
    """读取音频文件为 base64，并猜测 codec（wav/mp3/m4a）。"""
    ext = os.path.splitext(audio_path)[1].lower().lstrip(".")
    codec_map = {"wav": "wav", "mp3": "mp3", "m4a": "m4a", "aac": "aac"}
    codec = codec_map.get(ext, "wav")
    with open(audio_path, "rb") as f:
        data = f.read()
    return base64.b64encode(data).decode("ascii"), codec


def _ensure_clone_audio_duration(audio_path: str, max_sec: float = 15.0) -> str:
    """腾讯云 VRS 一句话声音复刻硬性要求 5-15s，超过会被拒 (AudioDurationExceedsLimit)。
    这里做兜底：若 > 15s 则用 pydub 截到 15s 内，返回处理后的文件路径（原文件不动）。

    解码失败（损坏/非音频）时不抛错，交给腾讯云返回更具体的错误信息。
    """
    try:
        from pydub import AudioSegment  # pydub 已在 tts.py 使用，复用
    except Exception:
        return audio_path  # 缺依赖时跳过裁剪
    try:
        ext = os.path.splitext(audio_path)[1].lower().lstrip(".") or "wav"
        audio = AudioSegment.from_file(audio_path, format=ext)
        duration_sec = len(audio) / 1000.0
        if duration_sec <= max_sec:
            return audio_path
        # 取中段（跳过头尾静音概率高一点的位置），但稳妥起见直接取前 max_sec
        trimmed = audio[: int(max_sec * 1000)]
        out_path = audio_path + f".trimmed.{ext}"
        trimmed.export(out_path, format=ext)
        logger.warning(
            "[vrs] 上传音频 %.2fs 超过 %ss, 已自动截取前 %ss 提交",
            duration_sec, max_sec, max_sec,
        )
        return out_path
    except Exception as e:
        logger.warning("[vrs] 音频时长检测/裁剪失败，原样提交: %s", e)
        return audio_path


def get_training_text() -> list[dict]:
    """获取 VRS 标准训练文本（前端可展示，引导用户录制）。"""
    client = _get_vrs_client()
    req = models.GetTrainingTextRequest()
    resp = client.GetTrainingText(req)
    # resp 是 SDK 对象，统一转 dict 解析
    data = json.loads(resp.to_json_string()).get("Data") or {}
    return data.get("TrainingTextList") or []


def create_clone_task(
    name: str,
    audio_path: str,
    voice_gender: int = 1,
    user_id: Optional[int] = None,
) -> VoiceCloneTask:
    """上传样本音频 -> 检测 -> 创建复刻任务，落库并返回任务记录。

    voice_gender: 1-男 2-女
    """
    client = _get_vrs_client()
    # 兜底：若上传音频 > 15s 自动截取前 15s，避免腾讯云 VRS 报
    # InvalidParameterValue.AudioDurationExceedsLimit。
    audio_path = _ensure_clone_audio_duration(audio_path, max_sec=15.0)
    audio_b64, codec = _read_audio_as_b64(audio_path)

    # 1) 音频质量检测 -> AudioId
    det_req = models.DetectEnvAndSoundQualityRequest()
    det_req.AudioData = audio_b64
    det_req.Codec = codec
    det_req.SampleRate = 16000
    det_req.TaskType = VRS_TASK_TYPE_ONESHOT
    det_req.TextId = "00001"
    det_req.TypeId = VRS_TYPE_ID_NORMAL
    try:
        det_resp = client.DetectEnvAndSoundQuality(det_req)
    except TencentCloudSDKException as e:
        raise RuntimeError(f"音频检测失败：{e.code} {e.message}")

    audio_id = (json.loads(det_resp.to_json_string()).get("Data") or {}).get("AudioId")
    if not audio_id:
        raise RuntimeError("音频检测未返回 AudioId，请更换更清晰的录音")

    # 2) 创建复刻任务
    session_id = uuid.uuid4().hex
    create_req = models.CreateVRSTaskRequest()
    create_req.SessionId = session_id
    create_req.VoiceName = name
    create_req.VoiceGender = voice_gender
    create_req.VoiceLanguage = VRS_LANG_ZH
    create_req.AudioIdList = [audio_id]
    create_req.Codec = codec
    create_req.SampleRate = 16000
    create_req.TaskType = VRS_TASK_TYPE_ONESHOT
    try:
        create_resp = client.CreateVRSTask(create_req)
    except TencentCloudSDKException as e:
        raise RuntimeError(f"创建复刻任务失败：{e.code} {e.message}")

    task_id = (json.loads(create_resp.to_json_string()).get("Data") or {}).get("TaskId")
    if not task_id:
        raise RuntimeError("创建复刻任务未返回 TaskId")

    # 3) 落库
    rec = VoiceCloneTask(
        name=name,
        task_id=task_id,
        sample_url=audio_path,
        status="training",
        created_by=user_id,
    )
    with SessionLocal() as db:
        db.add(rec)
        db.commit()
        db.refresh(rec)
    return rec


def query_task_status(rec_id: int) -> dict:
    """查复刻任务状态；若训练成功则把 VoiceType 写回库。

    返回 {status, voice_type, error_message, name}
    """
    with SessionLocal() as db:
        rec = db.get(VoiceCloneTask, rec_id)
        if not rec:
            raise RuntimeError("任务不存在")
        if rec.status == "succeeded":
            return {
                "status": rec.status,
                "voice_type": rec.voice_type,
                "error_message": rec.error_message,
                "name": rec.name,
            }
        if not rec.task_id:
            raise RuntimeError("任务缺少腾讯云 TaskId")

        client = _get_vrs_client()
        req = models.DescribeVRSTaskStatusRequest()
        req.TaskId = rec.task_id
        try:
            resp = client.DescribeVRSTaskStatus(req)
        except TencentCloudSDKException as e:
            return {
                "status": rec.status,
                "voice_type": rec.voice_type,
                "error_message": f"{e.code} {e.message}",
                "name": rec.name,
            }
        data = json.loads(resp.to_json_string()).get("Data") or {}
        # Status: 1-训练中 2-成功 3-失败（参考 VRS 回调约定）
        status_code = data.get("Status")
        if status_code == 2 or "VoiceType" in data:
            rec.status = "succeeded"
            rec.voice_type = data.get("VoiceType")
        elif status_code == 3:
            rec.status = "failed"
            rec.error_message = data.get("ErrorMsg") or "训练失败"
        else:
            rec.status = "training"
        db.commit()
        db.refresh(rec)
        return {
            "status": rec.status,
            "voice_type": rec.voice_type,
            "error_message": rec.error_message,
            "name": rec.name,
        }


def list_my_voices(user_id: Optional[int] = None) -> list[dict]:
    """列出我的复刻音色（含训练状态）。"""
    with SessionLocal() as db:
        q = db.query(VoiceCloneTask)
        if user_id is not None:
            q = q.filter(VoiceCloneTask.created_by == user_id)
        recs = q.order_by(VoiceCloneTask.id.desc()).all()
        return [
            {
                "id": r.id,
                "name": r.name,
                "status": r.status,
                "voice_type": r.voice_type,
                "task_id": r.task_id,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in recs
        ]
