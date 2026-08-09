"""
数字人 / 仿真人口播音频生成工具

使用腾讯云 TTS（TextToVoice，内网直连、稳定、音质好）合成 mp3，保存到
本地 /data/materials/voices/，再由数字人链路通过 VOD 上传后回传给 Kling
avatar_i2v / lip_sync 做对口型。

注意：之前用 edge-tts 在服务器环境会被微软网关返回 403（WSServerHandshakeError），
故改为腾讯云 TTS（账号已具备密钥与额度）。长文本（>200 字）按句分段合成后
用 pydub 拼接成一个完整 mp3，保证数字人口播不被截断、视频时长跟随音频。
"""

from __future__ import annotations

import asyncio
import io
import os
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from pydub import AudioSegment

from app.config import get_settings

# 腾讯云 TTS 中文精品音色（VoiceType 为 int）。
# 字段：id 兼容旧前端、name 中文展示、voice_type 腾讯云数字音色、lang 语言。
#
# ⚠️ 重要：voice_type 必须指向腾讯云真实存在的精品音色，否则合成出来的
# 声音性别/场景与预期不符（旧代码把 101001/101013/101020 等填错，导致
# “标男声却听成女声”）。下面每个 id 都按“晓X=女声，云X=男声”且尽量贴近
# 场景标签，映射到腾讯云官方精品音色表（智X 系列，见腾讯云 TTS 音色文档）。
TENCENT_TTS_VOICES: list[dict] = [
    # === 普通话精品（女） ===
    {"id": "zh-CN-XiaoxiaoNeural", "name": "晓晓（女·温柔）",    "voice_type": 101001, "lang": "zh", "gender": "female", "tag": "温柔"},  # 智瑜·情感女声
    {"id": "zh-CN-XiaoyiNeural",   "name": "晓伊（女·活力）",    "voice_type": 101003, "lang": "zh", "gender": "female", "tag": "活力"},  # 智美·女声
    {"id": "zh-CN-XiaomengNeural", "name": "晓梦（女·儿童）",    "voice_type": 101016, "lang": "zh", "gender": "female", "tag": "童声"},  # 智甜·女童声
    {"id": "zh-CN-XiaomoNeural",   "name": "晓墨（女·情感）",    "voice_type": 101002, "lang": "zh", "gender": "female", "tag": "情感"},  # 智聆·女声（已试听确认女声）
    {"id": "zh-CN-XiaoyanNeural",  "name": "晓颜（女·多情感）",  "voice_type": 101005, "lang": "zh", "gender": "female", "tag": "情感"},  # 智莉·女声
    {"id": "zh-CN-XiaozhenNeural", "name": "晓珍（女·多情感）",  "voice_type": 101008, "lang": "zh", "gender": "female", "tag": "情感"},  # 智琪·女声
    {"id": "zh-CN-XiaoxuanNeural", "name": "晓萱（女·甜美）",    "voice_type": 101009, "lang": "zh", "gender": "female", "tag": "甜美"},  # 智芸·女声（已试听确认女声）
    # === 普通话精品（男） ===
    {"id": "zh-CN-YunxiNeural",    "name": "云希（男·沉稳）",    "voice_type": 101004, "lang": "zh", "gender": "male", "tag": "沉稳"},  # 智云·通用男声
    {"id": "zh-CN-YunjianNeural",  "name": "云健（男·新闻播报）","voice_type": 101013, "lang": "zh", "gender": "male", "tag": "新闻播报"},  # 智辉·新闻男声（已试听确认男声）
    {"id": "zh-CN-YunyangNeural",  "name": "云扬（男·专业解说）","voice_type": 101020, "lang": "zh", "gender": "male", "tag": "专业"},  # 智刚·新闻男声
    {"id": "zh-CN-YunfengNeural",  "name": "云枫（男·阳光）",    "voice_type": 101010, "lang": "zh", "gender": "male", "tag": "阳光"},  # 智华·男声
    {"id": "zh-CN-YunhaoNeural",   "name": "云皓（男·解说）",    "voice_type": 101024, "lang": "zh", "gender": "male", "tag": "解说"},  # 智皓·男声（已试听确认男声）
    {"id": "zh-CN-YunxiaNeural",   "name": "云夏（男·温暖）",    "voice_type": 101018, "lang": "zh", "gender": "male", "tag": "温暖"},  # 智靖·男声
    {"id": "zh-CN-YunzeNeural",    "name": "云泽（男·新闻）",    "voice_type": 101021, "lang": "zh", "gender": "male", "tag": "新闻"},  # 智瑞·新闻男声（已试听确认男声）
    {"id": "zh-CN-YunjieNeural",   "name": "云杰（男·叙事）",    "voice_type": 101029, "lang": "zh", "gender": "male", "tag": "叙事"},  # 智凯·男声
]

# 默认音色：晓晓（女·温柔）
DEFAULT_VOICE_ID = "zh-CN-XiaoxiaoNeural"

# 文件落盘目录：默认 settings.storage_path / voices，落在 FastAPI 静态
# 服务目录（/static/materials）下，方便 Kling 通过 public_base_url 公网拉取。
# 也可被 env AI_PUBLISH_VOICES_DIR 覆盖。
_settings = get_settings()
VOICES_DIR = Path(
    os.getenv("AI_PUBLISH_VOICES_DIR", str(_settings.storage_path / "voices"))
)
VOICES_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class TTSResult:
    audio_path: str
    audio_url: str
    voice_id: str
    duration_sec: float
    file_size: int


def list_voices() -> list[dict]:
    """前端音色下拉用（仅返回前端需要的字段）。"""
    return [
        {"id": v["id"], "name": v["name"], "gender": v.get("gender"), "tag": v.get("tag")}
        for v in TENCENT_TTS_VOICES
    ]


def resolve_voice_id(voice_id: Optional[str]) -> dict:
    """校验传入 voice_id；非法或为空时回退到默认，返回完整音色配置。

    复刻音色约定 id 格式为 ``clone:<voice_type>``（voice_type 为腾讯云 VRS
    训练得到的整数），识别后返回带整数 voice_type 的配置，供 synthesize_speech
    走复刻合成路径。
    """
    if voice_id and str(voice_id).startswith("clone:"):
        try:
            vt = int(str(voice_id).split(":", 1)[1])
            return {"id": voice_id, "name": "我的声音", "voice_type": vt, "lang": "zh", "gender": "custom", "tag": "复刻"}
        except (ValueError, IndexError):
            pass
    for v in TENCENT_TTS_VOICES:
        if v["id"] == voice_id:
            return v
    for v in TENCENT_TTS_VOICES:
        if v["id"] == DEFAULT_VOICE_ID:
            return v
    return TENCENT_TTS_VOICES[0]


def _get_tts_client():
    """构造腾讯云 TTS 客户端（内网直连，使用与 VOD 相同的密钥）。

    密钥来源与 VOD 适配器保持一致：优先用 provider config（ai_runtime.json /
    环境变量）里的 tencent_vod_secret_id / tencent_vod_secret_key。
    """
    from tencentcloud.common import credential
    from tencentcloud.common.profile.client_profile import ClientProfile
    from tencentcloud.common.profile.http_profile import HttpProfile
    from tencentcloud.tts.v20190823 import tts_client

    from app.services.ai_provider_config_service import AiProviderConfigService

    cfg = AiProviderConfigService()
    secret_id = cfg.get_field_value("tencent_vod_secret_id") or ""
    secret_key = cfg.get_field_value("tencent_vod_secret_key") or ""
    if not secret_id or not secret_key:
        raise RuntimeError("缺少腾讯云密钥（tencent_vod_secret_id / tencent_vod_secret_key）")

    cred = credential.Credential(secret_id, secret_key)
    http_profile = HttpProfile()
    http_profile.endpoint = "tts.tencentcloudapi.com"
    client_profile = ClientProfile()
    client_profile.httpProfile = http_profile
    return tts_client.TtsClient(cred, "ap-guangzhou", client_profile)


def _sanitize_for_tts(text: str) -> str:
    """腾讯云 TTS 不支持部分控制字符，做一次保守清洗。"""
    if not text:
        return ""
    # 去掉不可见控制字符，保留中文/英文/数字/常见标点
    pattern = r"[^\u4e00-\u9fffA-Za-z0-9\s，。！？、；：\"'《》（）()…\-—\.,!?;:']"
    cleaned = re.sub(pattern, " ", text)
    return re.sub(r"\s+", " ", cleaned).strip()


def _synthesize_one(text: str, voice_type: int, lang: str) -> bytes:
    """调用腾讯云 TTS 合成单段 mp3 二进制（同步，在线程内跑）。"""
    from tencentcloud.tts.v20190823 import models

    client = _get_tts_client()
    req = models.TextToVoiceRequest()
    req.VoiceType = voice_type
    req.Codec = "mp3"
    req.SampleRate = 16000
    req.Text = text
    # 中文/粤语/台普语言参数：腾讯云 TTS 用 PrimaryLanguage 区分
    lang_map = {"zh": 1, "zh-HK": 2, "zh-TW": 3}
    req.PrimaryLanguage = lang_map.get(lang, 1)
    req.SessionId = uuid.uuid4().hex
    resp = client.TextToVoice(req)
    if not resp.Audio:
        raise RuntimeError(f"腾讯云 TTS 返回空音频: text={text[:40]!r}")
    import base64
    return base64.b64decode(resp.Audio)


def _split_text(text: str, max_len: int = 150) -> list[str]:
    """按标点/空格把长文本拆成 ≤ max_len 字的片段（腾讯云 TTS 单次上限 300 字，
    取 150 留余量）。拆分优先级：句号/问号/感叹号/省略号 > 逗号/分号 > 空格。
    """
    if len(text) <= max_len:
        return [text] if text.strip() else []

    boundaries = ["。", "！", "？", "…", "；", "，", "、", " ", "\n"]
    segments: list[str] = []
    buf = ""

    for ch in text:
        buf += ch
        if ch in "。！？…；，、\n" and len(buf) >= max_len * 0.5:
            segments.append(buf.strip())
            buf = ""
        elif len(buf) >= max_len:
            cut = max_len
            for i in range(len(buf) - 1, max(0, len(buf) - max_len), -1):
                if buf[i] in boundaries:
                    cut = i + 1
                    break
            segments.append(buf[:cut].strip())
            buf = buf[cut:]

    if buf.strip():
        segments.append(buf.strip())
    return [s for s in segments if s]


def synthesize_speech(
    text: str,
    voice_id: Optional[str] = None,
    *,
    voice_type: Optional[int] = None,
    rate: str = "+0%",
    volume: str = "+0%",
    prefix: str = "tts",
    segment: bool = True,
) -> TTSResult:
    """
    同步入口：合成 mp3 → 写入 VOICES_DIR → 返回本地路径与可外网访问的 URL。

    - voice_id: 标准音色 id（查 TENCENT_TTS_VOICES 表）
    - voice_type: 复刻音色整数 ID（腾讯云 VRS 训练后得到），优先级高于 voice_id

    长文本（>150 字）按句分段合成后用 pydub 拼接成一个完整 mp3，
    这样数字人口播不会被截断，Kling 也能按完整音频时长生成对口型视频。
    """
    # 复刻音色（VRS 训练得到的整数 voice_type）优先级最高
    if voice_type is not None:
        voice_cfg = {"id": f"clone:{voice_type}", "voice_type": int(voice_type), "lang": "zh"}
    else:
        voice_cfg = resolve_voice_id(voice_id)
    voice_type = voice_cfg["voice_type"]
    lang = voice_cfg.get("lang", "zh")
    cleaned = _sanitize_for_tts(text)
    if not cleaned:
        raise ValueError("TTS 文本为空，无法合成。")

    import logging
    logger = logging.getLogger(__name__)

    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None

    def _run_in_thread(fn):
        if current_loop is not None:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(fn).result()
        return fn()

    is_clone_voice = str(voice_cfg.get("id", "")).startswith("clone:") or voice_cfg.get("voice_source") == "clone"
    # 复刻音色（VRS 训练）单次合成对音频时长有限制（约 20s），需拆得
    # 更细；标准精品音色放宽到 150 字一段。
    if is_clone_voice:
        segment_max_len = 60
    else:
        segment_max_len = 150

    if segment and len(cleaned) > segment_max_len:
        parts = _split_text(cleaned, max_len=segment_max_len)
        logger.info(
            "[tts] 长文本分段合成: 共 %d 段 (max_len=%d, clone=%s)",
            len(parts), segment_max_len, is_clone_voice,
        )
        chunks: list[AudioSegment] = []
        for idx, part in enumerate(parts):
            try:
                audio_b64 = _run_in_thread(lambda p=part: _synthesize_one(p, voice_type, lang))
            except Exception as e:
                # 段级合成失败（极有可能 = 单段音频时长超限）→ 再拆半重试一次
                err_msg = str(e)
                if "AudioDurationExceedsLimit" in err_msg or "exceeds the maximum" in err_msg:
                    sub_parts = _split_text(part, max_len=max(20, len(part) // 2))
                    logger.warning(
                        "[tts] 段 %d 触发时长超限，自动拆为 %d 子段重试",
                        idx + 1, len(sub_parts),
                    )
                    sub_audios: list[AudioSegment] = []
                    for sp in sub_parts:
                        sa = _run_in_thread(lambda p=sp: _synthesize_one(p, voice_type, lang))
                        if not sa:
                            raise RuntimeError(f"腾讯云 TTS 子段合成失败：段{idx + 1}")
                        sub_audios.append(AudioSegment.from_file(io.BytesIO(sa), format="mp3"))
                    seg = sub_audios[0]
                    for c in sub_audios[1:]:
                        seg += AudioSegment.silent(duration=150) + c
                    chunks.append(seg)
                    continue
                raise
            if not audio_b64:
                raise RuntimeError(f"腾讯云 TTS 分段合成失败：第 {idx + 1} 段")
            chunks.append(AudioSegment.from_file(io.BytesIO(audio_b64), format="mp3"))
        merged = chunks[0]
        for c in chunks[1:]:
            # 段间加 150ms 静音，避免语句黏连
            merged += AudioSegment.silent(duration=150) + c
        buffer = io.BytesIO()
        merged.export(buffer, format="mp3", bitrate="64k")
        audio_bytes = buffer.getvalue()
    else:
        try:
            audio_bytes = _run_in_thread(
                lambda: _synthesize_one(cleaned, voice_type, lang)
            )
        except Exception as e:
            # 单段也超长（未达分段阈值但实际合成超限）→ 强制拆成 2 段再试
            err_msg = str(e)
            if "AudioDurationExceedsLimit" in err_msg or "exceeds the maximum" in err_msg:
                logger.warning("[tts] 单段时长超限，强制拆为 2 段重试")
                parts = _split_text(cleaned, max_len=max(30, len(cleaned) // 2))
                sub_audios: list[AudioSegment] = []
                for sp in parts:
                    sa = _run_in_thread(lambda p=sp: _synthesize_one(p, voice_type, lang))
                    if not sa:
                        raise RuntimeError("腾讯云 TTS 单段重试合成失败")
                    sub_audios.append(AudioSegment.from_file(io.BytesIO(sa), format="mp3"))
                merged = sub_audios[0]
                for c in sub_audios[1:]:
                    merged += AudioSegment.silent(duration=150) + c
                buf = io.BytesIO()
                merged.export(buf, format="mp3", bitrate="64k")
                audio_bytes = buf.getvalue()
            else:
                raise

    if not audio_bytes:
        raise RuntimeError(f"腾讯云 TTS 合成失败：voice={voice_cfg['id']}, text={cleaned[:60]!r}")

    fname = f"{prefix}_{int(time.time())}_{uuid.uuid4().hex[:8]}.mp3"
    out_path = VOICES_DIR / fname
    out_path.write_bytes(audio_bytes)

    # 用 pydub 精确计算时长
    try:
        seg = AudioSegment.from_file(io.BytesIO(audio_bytes), format="mp3")
        duration_sec = round(len(seg) / 1000.0, 2)
    except Exception:
        duration_sec = round(len(audio_bytes) * 8 / 32_000, 2)

    return TTSResult(
        audio_path=str(out_path),
        audio_url=f"/static/materials/voices/{fname}",  # 由 FastAPI 静态服务映射
        voice_id=voice_cfg["id"],
        duration_sec=duration_sec,
        file_size=len(audio_bytes),
    )
