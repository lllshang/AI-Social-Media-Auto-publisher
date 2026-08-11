"""
腾讯云「声音复刻」（VRS, Voice Replica Service）服务

支持双模式：
  A) 基础版（TaskType=1，默认）：上传清晰中文录音 -> 音质检测拿 AudioId ->
     创建任务。不依赖训练文本，走独立额度。
  B) 一句话复刻（TaskType=5，高级版）：GetTrainingText 拿 TextId -> 用户跟读
     -> 音质检测拿 AudioId -> 创建任务。音色更自然，但消耗独立额度。

  模式由腾讯云配置表里的 `vrs_task_type` 控制（默认 1=基础版）。
  充值开通一句话版额度后，把该值改成 5 即可无缝切回高级版。

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


# 复刻模式：
#   VRS_TASK_TYPE_BASIC = 1  -> 基础版（默认）。不依赖训练文本，独立额度，
#                               配额更宽松，适合先跑通流程；训练质量略低于一句话版。
#   VRS_TASK_TYPE_ONESHOT = 5 -> 一句话复刻（高级版）。需先 GetTrainingText 拿
#                               TextId 让用户跟读，再 Detect + CreateVRSTask。
#                               音色更自然，但消耗"一句话版"独立额度（易耗尽）。
VRS_TASK_TYPE_BASIC = 1
VRS_TASK_TYPE_ONESHOT = 5

# 当前默认模式：基础版。充值开通一句话版额度后，把腾讯云配置表里
# `vrs_task_type` 改成 5 即可无缝切回高级版，无需改代码。
VRS_TASK_TYPE_DEFAULT = VRS_TASK_TYPE_BASIC
# 音频类型（TypeId）：1-环境检测(只判环境噪声,不登记样本,不返回AudioId)
#                    2-音质检测(含文本相似度校验,通过后才返回AudioId供创建任务)
# 一句话复刻创建任务必传 AudioIdList,因此检测必须用 TypeId=2 才能拿到 AudioId。
VRS_TYPE_ID_ENV = 1
VRS_TYPE_ID_QUALITY = 2
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


def get_current_task_type() -> int:
    """读取当前复刻模式（基础版=1 / 一句话复刻=5）。

    优先级：环境变量 VRS_TASK_TYPE > JSON 配置 `vrs_task_type`（与厂商配置同文件）> 默认基础版(1)。

    调用方统一走 ``AiProviderConfigService.get_vrs_task_type()``，避免散落多处
    各自推断路径，确保后台管理 UI 写入的值立即生效。
    """
    try:
        from app.services.ai_provider_config_service import AiProviderConfigService

        info = AiProviderConfigService().get_vrs_task_type()
        v = int(info.get("value") or 1)
        if v in (VRS_TASK_TYPE_BASIC, VRS_TASK_TYPE_ONESHOT):
            return v
    except Exception as e:  # noqa: BLE001 - 兜底，保证旧调用不阻塞
        logger.debug("[vrs-mode] 通过 service 读取失败，使用兜底逻辑: %s", e)
        env_val = os.environ.get("VRS_TASK_TYPE", "").strip()
        if env_val in ("1", "5"):
            return int(env_val)
    return VRS_TASK_TYPE_DEFAULT



def _read_audio_as_b64_with_codec(audio_path: str, codec: str) -> tuple[str, str]:
    """读取音频文件为 base64，使用指定 codec（用于裁剪后已被转换为 wav 的文件）。"""
    with open(audio_path, "rb") as f:
        data = f.read()
    return base64.b64encode(data).decode("ascii"), codec


def _read_audio_as_b64(audio_path: str) -> tuple[str, str]:
    """读取音频文件为 base64，并猜测 codec（wav/mp3/m4a）。"""
    ext = os.path.splitext(audio_path)[1].lower().lstrip(".")
    codec_map = {"wav": "wav", "mp3": "mp3", "m4a": "m4a", "aac": "aac"}
    codec = codec_map.get(ext, "wav")
    with open(audio_path, "rb") as f:
        data = f.read()
    return base64.b64encode(data).decode("ascii"), codec


def _ensure_clone_audio_duration(audio_path: str, max_sec: float = 15.0) -> tuple[str, str]:
    """腾讯云 VRS 一句话声音复刻硬性要求 5-15s，超过会被拒 (AudioDurationExceedsLimit)。
    这里做兜底：若 > 15s 则用 pydub 截到 15s 内，返回 (处理后文件路径, codec)。

    关键修正：pydub 写 m4a/aac 在某些 ffmpeg 编译版本下 moov atom 写不完整，
    会留下 0 字节损坏文件导致后续 ffmpeg 读取再次失败。这里统一把裁剪后的音频
    导出为 wav 16k mono 并返回 codec='wav'，腾讯云 VRS 完全支持 wav 格式。

    返回 (path, codec)；若无需裁剪，codec 维持原格式。

    解码失败（损坏/非音频）时不抛错，交给腾讯云返回更具体的错误信息。
    """
    try:
        from pydub import AudioSegment  # pydub 已在 tts.py 使用，复用
    except Exception:
        # 缺 pydub 时不裁剪也不改 codec，按原样返回
        return audio_path, _codec_of(audio_path)
    try:
        ext = os.path.splitext(audio_path)[1].lower().lstrip(".") or "wav"
        audio = AudioSegment.from_file(audio_path, format=ext)
        duration_sec = len(audio) / 1000.0
        if duration_sec <= max_sec:
            return audio_path, _codec_of(audio_path)
        # 取前 max_sec
        trimmed = audio[: int(max_sec * 1000)]
        # 统一重采样为 16kHz mono（VRS 推荐规格），并统一写 wav 避免 m4a 兼容性问题
        trimmed = trimmed.set_channels(1).set_frame_rate(16000)
        out_path = audio_path + ".trimmed.wav"
        trimmed.export(out_path, format="wav")
        logger.warning(
            "[vrs] 上传音频 %.2fs 超过 %ss, 已自动截取前 %ss 并转 wav 16k mono 提交",
            duration_sec, max_sec, max_sec,
        )
        return out_path, "wav"
    except Exception as e:
        logger.warning("[vrs] 音频时长检测/裁剪失败，原样提交: %s", e)
        return audio_path, _codec_of(audio_path)


def _codec_of(audio_path: str) -> str:
    ext = os.path.splitext(audio_path)[1].lower().lstrip(".")
    return {"wav": "wav", "mp3": "mp3", "m4a": "m4a", "aac": "aac"}.get(ext, "wav")


# 腾讯云训练文本里常见的、会让 ASR 识别出错的"低质量"汉字集合
# （用户能读、但 ASR 在它的语料里几乎没见过，会被识别成完全无关的常见字）
# 这里用黑名单的方式：只要包含这些字就直接换一条文本。
_VRS_LOW_FREQ_CHARS = set(
    "臼毂鬣鼙鼗龠龢龥龠鸠鸢鸩鸪鸫鸬鸲鸱鸶鸷"
    "龀龅龆龈龉龊龋龌龉龊龋龌麾黛黹黻黼黾鼍"
    "呱呖咦咧咱咭咯咯咪咤哕哙哚哜唛唠唢唣唤唳唿啁啐"
    "啁啐啕啖啜啭啁啁啷喁喆喈喟喤喾嗞嗬嗳"
    "嗒嗌嗍嗨嗦嘣嘬嘭噗嘹嘬嚣嚯囔圊圙圜坨"
    "垚垲埝堞堙堠墀墉墚墀壸壷壹夔夔夔"
    "弑彖彘忝怅怍怿恂恚恧恂恚恧恿悃悝惘"
    "愠愦戆戾扃扈拊拚拈挹捭掊掭掾揶"
    "搒摈榱欤歆殁殇殒毓氤氲沣沭沱"
    "洹洧洹洧浐涑涞淅淙淝淠淦淙淝"
    "渑湍湜溲滏潞潍潞澉澌澍濂濮"
    "炅炖炜炟烊烨焐焱煜煦熹"
    "犍犏犒狍獬獬獬獬獬獬獬獬獬獬獬獬"
    "獬獬玟玢玥珂珈珥珲璎璐疃痖瘕瘥瘭"
    "癞癯皤盍盱眍眙眩眭眳睁睚睨睢睥睿"
    "碲碹碥磔磴礅禊穑穗穸穸竽笃笕笞筚"
    "筱箦箧箸箴篑篆篪簦籴粲糁糅"
    "紬綮縻纛绔绗绺绲缍缑缒缗"
    "翚耦聃聍聱肓朊朐朊胱胭腴腒腴腒腴"
    "腑腴腱腴腴腴腴腴腴腴"
    "臁舢舭艏艨苻苣苜茈茚苓苕"
    "苣苟茕茚茔茕茔茕茕茕"
    "莅莩莘莪菟菽菹萁萑萦蒇蒯"
    "蒹蒽蓐蓍蓐蓍蓐蓍蓐蓍蓍蓍蓍蓍蓍蓍"
    "蕤蕞蕤薮藁藓蘧蘩蘸蘧蘩蘸蘧蘩蘸蘧蘩蘸"
    "虍虬虮虬虮虬虮虬虮虬虮虬虮虬虮虬虮"
    "蚍蚋蚝蚬蚰蜒蚱蚍蚋蚝蚬蚰蜒蚱蚍蚋蚝蚬蚰蜒蚱蚍蚋蚝蚬"
    "蜊蜍蜾蝾螟螫螬螭螵螨螽"
    "蟑蟊蟠蟊蟠蟊蟠蟊蟠蟊蟠蟊蟠"
    "蟮蟊蟠蟊蟠蟊蟠蟊蟠蟊蟠蟊蟠"
    "蠹跗跞踬踱踬踬踬踬踬踬踬踬"
    "踮踯踺蹁蹒蹊蹐蹕蹙蹚蹦"
    "蹩蹬蹭蹰蹶蹹蹻躏躔躐躜躞"
    "躞躞躞躞躞躞躞躞躞躞躞"
    "轹轱轲轳轵轶轸轹轱轲轳"
    "辘辚辜辏辘辚辜辏辘辚辜辏"
    "迤迮迸邸郅郇郐郄郏郐郄郏郐郄郏"
    "鄄鄞鄣鄱鄹鄽酊酝酞酚酝酞酚酝酞酚"
    "酰酲醚醛醚醛醚醛醚醛醚醛"
    "鎏鏊鏖鏖鏖鏖鏖鏖鏖鏖鏖鏖"
    "鐾鑽鑾鑾鑾鑾鑾鑾鑾鑾鑾"
    "镟镠镮镯镯镯镯镯镯镯镯"
    "闾阍阏阖阚阙阛阱陟陧陬"
    "陲陴隈隚隳隹雎雒雒雒雒雒雒"
    "雠雒雠雒雠雒雠雒雠雠雠"
    "靼靽鞒鞔鞯鞣鞲鞴韪韫"
    "頎颉颍颎颏颐颔颚颛颞"
    "颡颢颥颦虺虼虺虼虺虼虺虼虺"
    "饧饨饩饪饫饬饴饷饽饾馀"
    "馁馂馄馇馊馌馐馑馔馕"
    "骱骶髅髁髂髑髓體髟鬓鬈"
    "鬟鬣魄魇魉魍魑魈魍魑魈魍魑"
    "鲂鲅鲈鲋鲊鲞鲦鲧鲬鲲"
    "鲰鲱鲲鲳鲴鲵鲶鲷鲺鲽鳁鳂"
    "鳊鳎鳏鳐鳓鳔鳕鳖鳜鳟"
    "鱿鱿鱿鱿鱿鱿鱿鱿鱿鱿鱿"
    "鳣鳤鳣鳤鳣鳤鳣鳤鳣鳤"
    "鞴鞴鞴鞴鞴鞴鞴鞴鞴鞴"
)


def _is_friendly_text(text: str) -> bool:
    """判断文本是否适合作为 VRS 一句话复刻的训练文本。

    规则（任一不满足视为不友好）：
    1) 字数在 7-18 之间（短于7一句话不自然，长于18超15s 录音容易过紧）
    2) 不含腾讯云 ASR 经常识别错的"低质量"汉字（黑名单）
    3) 不能是单字重复（"啊啊啊啊"）或纯标点
    """
    if not text:
        return False
    t = text.strip()
    if len(t) < 7 or len(t) > 18:
        return False
    if any(c in _VRS_LOW_FREQ_CHARS for c in t):
        return False
    # 全部是同一字 / 全是标点 / 全是英数字
    if len(set(c for c in t if not c.isspace())) <= 2:
        return False
    # 标点占比 > 30%
    punct = sum(1 for c in t if not c.isalnum() and not c.isspace())
    if punct / max(len(t), 1) > 0.3:
        return False
    return True


def _format_vrs_detect_detail(det_data: dict) -> str:
    """把腾讯云 VRS 音频检测的原始响应整理成中文可读提示。

    DetectEnvAndSoundQuality 返回结构不保证字段稳定，这里做容错：
    - 优先从 DetectionTip 里挑出 PronAccuracy=-1/0 的字（漏读/错读/未识别）
    - 退而从 Details / DetailList 拿其他原因
    - 都没有则原样 dump
    """
    if not det_data:
        return "未返回任何检测数据"

    det_code = det_data.get("DetectionCode")
    det_msg = det_data.get("DetectionMsg") or ""
    head_parts = []
    if det_code not in (None, 0, "0"):
        head_parts.append(f"检测未通过(code={det_code})")
    if det_msg and det_msg.lower() not in ("success", "ok"):
        # 把英文检测结论翻译成人话（基于腾讯云官方 DetectionCode 常见枚举）
        head_parts.append(_humanize_detection_msg(det_msg))

    # 1) DetectionTip：每个字的 PronAccuracy 和 Tag
    tip = det_data.get("DetectionTip")
    tip_msgs = []
    if isinstance(tip, list) and tip:
        missed, misread, noisy = [], [], []
        for it in tip:
            if not isinstance(it, dict):
                continue
            word = it.get("Word") or it.get("Character") or ""
            acc = it.get("PronAccuracy")
            tag = it.get("Tag")
            # PronAccuracy: -1=未识别/未读到, 0=读到但发音不准, 1=正常
            if acc in (-1, "-1"):
                missed.append(word or "·")
            elif acc in (0, "0"):
                misread.append(word or "·")
            # Tag: 1=多读 2=漏读 3=背景音（按 SDK 文档约定，具体值以腾讯云实际为准）
            if tag == 1:
                noisy.append(word or "·")
        if missed:
            tip_msgs.append(f"漏读或未识别的字：{', '.join(missed[:12])}")
        if misread:
            tip_msgs.append(f"发音不准的字：{', '.join(misread[:12])}")
        if noisy:
            tip_msgs.append(f"可能被识别为多读的字：{', '.join(noisy[:12])}")

    # 2) Details / DetailList（其他原因）
    for key in ("Details", "DetailList", "Detail"):
        items = det_data.get(key)
        if isinstance(items, list) and items:
            parts = []
            for it in items:
                if isinstance(it, dict):
                    name = it.get("Name") or it.get("Type") or it.get("Key") or ""
                    desc = it.get("Description") or it.get("Desc") or it.get("Msg") or it.get("Message") or ""
                    score = it.get("Score") if "Score" in it else None
                    if desc:
                        parts.append(f"{name}：{desc}" if name else str(desc))
                    elif score is not None:
                        parts.append(f"{name} 得分 {score}")
                elif isinstance(it, str):
                    parts.append(it)
            if parts:
                tip_msgs.append("；".join(parts))

    # 3) 综合 Score
    score = det_data.get("Score") or det_data.get("TotalScore")
    if score is not None and not tip_msgs:
        tip_msgs.append(f"综合检测得分 {score}")

    body = "；".join(tip_msgs) if tip_msgs else ""
    if head_parts and body:
        return "；".join(head_parts) + "；" + body
    if head_parts:
        return "；".join(head_parts)
    if body:
        return body
    # 兜底
    import json
    return f"原始检测数据：{json.dumps(det_data, ensure_ascii=False)}"


# 腾讯云 DetectionMsg 常见英文结论的中文翻译
_DET_MSG_ZH = {
    "voice detection failed (usually missed read, misread, or multiple read)":
        "录音文本识别失败（通常是漏读、错读或重复读）",
    "voice detection failed": "音频检测失败",
    "audio format error": "音频格式不符合要求（需 wav/mp3/m4a，5-15秒）",
    "background noise too loud": "背景噪音过大",
    "volume too low": "音量过低",
    "volume too high": "音量过高",
}


def _humanize_detection_msg(msg: str) -> str:
    if not msg:
        return ""
    lower = msg.strip().lower()
    if lower in _DET_MSG_ZH:
        return _DET_MSG_ZH[lower]
    for k, v in _DET_MSG_ZH.items():
        if k in lower:
            return v
    return msg


def get_training_text(task_type: int = VRS_TASK_TYPE_ONESHOT) -> list[dict]:
    """获取 VRS 标准训练文本列表（前端可展示，引导用户录制）。

    task_type 必须传 VRS_TASK_TYPE_ONESHOT(5)：一句话复刻模式。
    注意：不传或传 1 时腾讯云会返回失效的固定 TextId（00001~00020，已过期 7 天），
    导致 DetectEnvAndSoundQuality 报 'TextId expires 7 days'。传 5 时返回
    UUID 格式的有效 TextId。
    """
    client = _get_vrs_client()
    req = models.GetTrainingTextRequest()
    req.TaskType = task_type
    resp = client.GetTrainingText(req)
    # resp 是 SDK 对象，统一转 dict 解析
    data = json.loads(resp.to_json_string()).get("Data") or {}
    return data.get("TrainingTextList") or []


def get_training_text_pair() -> tuple[str, str]:
    """取一个可用的训练文本对 (TextId, TextContent)。

    腾讯云 VRS 一句话复刻（TaskType=5）要求：
    - TextId 必须从 GetTrainingText 动态获取，不能硬编码
    - 用户**必须照着该 TextId 对应的文本内容朗读**，否则音频检测失败
    - TextId 7 天过期 / 使用一次后失效，所以每次复刻都要重新获取

    返回第一个文本的 (TextId, TextContent)，供前端展示给用户跟读。
    """
    items = get_training_text()
    if not items:
        raise RuntimeError("腾讯云未返回任何训练文本，请稍后重试")
    # 优先挑：仅含常用汉字（白名单）+ 字数 7–18 的文本
    # 原因：腾讯云训练文本池里有大量含生僻字（臼、毂、己、哒 等）的句子，
    # 用户的麦克风能正常录到，但腾讯云 ASR 在它的语料里几乎没见过这些字，
    # 会把它们识别成完全无关的常见词（比如"臼/毂/哒"被听成"牙/部/很"），
    # 导致 PronAccuracy 全部 -1、判定为漏读，复刻失败。
    # 过滤后只留"用户读什么、ASR 就能识别什么"的句子。
    good = [it for it in items if _is_friendly_text(it.get("Text") or "")]
    candidates = good or items
    first = candidates[0]
    return first.get("TextId"), first.get("Text", "")


def create_clone_task(
    name: str,
    audio_path: str,
    voice_gender: int = 1,
    text_id: str | None = None,  # 仅一句话复刻（TaskType=5）需要：前端展示的训练文本对应的 TextId；
                                  # 传进来则必须用它去检测，否则会因"对照文本不一致"全部漏读。
                                  # 基础版（TaskType=1）忽略此参数。
    user_id: Optional[int] = None,
    task_type: Optional[int] = None,  # 复刻模式；不传则读配置表默认（基础版）
) -> VoiceCloneTask:
    """上传样本音频 -> 检测 -> 创建复刻任务，落库并返回任务记录。

    voice_gender: 1-男 2-女
    task_type:    VRS_TASK_TYPE_BASIC(1)=基础版 / VRS_TASK_TYPE_ONESHOT(5)=一句话复刻
    """
    if task_type is None:
        task_type = get_current_task_type()
    is_oneshot = (task_type == VRS_TASK_TYPE_ONESHOT)
    client = _get_vrs_client()
    # 兜底：若上传音频 > 15s 自动截取前 15s 并转 wav，避免腾讯云 VRS 报
    # InvalidParameterValue.AudioDurationExceedsLimit 同时规避 pydub 写 m4a
    # 损坏文件 (moov atom not found) 的问题。
    audio_path, codec = _ensure_clone_audio_duration(audio_path, max_sec=15.0)
    # 诊断日志（临时）：确认浏览器录音到后端的音频是否真的有内容、采样率/音量是否正常
    try:
        from pydub import AudioSegment
        seg = AudioSegment.from_file(audio_path)
        samples = seg.get_array_of_samples()
        import statistics
        rms = (statistics.fmean((s * s for s in samples)) ** 0.5) if samples else 0
        # 计算有声占比（绝对值 > 阈值的样本比例），判断是不是大部分时间静音
        if samples:
            thr = max(int(rms * 0.2), 50)
            voiced = sum(1 for s in samples if abs(s) > thr)
            voiced_ratio = voiced / len(samples)
        else:
            voiced_ratio = 0.0
        logger.warning(
            "[vrs-diag] mode=%s codec=%s 时长=%.2fs 采样率=%dHz 声道=%d RMS=%d/32767 有声占比=%.1f%%",
            "oneshot" if is_oneshot else "basic", codec, len(seg) / 1000.0,
            seg.frame_rate, seg.channels, int(rms), voiced_ratio * 100,
        )
    except Exception as e:
        logger.warning("[vrs-diag] 音频诊断失败: %s", e)
    audio_b64, _ = _read_audio_as_b64_with_codec(audio_path, codec)

    # 一句话复刻（TaskType=5）需要训练文本 TextId 做 ASR 对照；基础版不需要。
    if is_oneshot:
        # 动态获取 TextId：腾讯云 VRS 一句话复刻要求 TextId 必须从 GetTrainingText
        # 取得，不能硬编码（7 天过期 / 用一次失效）。且该 TextId 对应的文本就是
        # 用户需要朗读的内容（前端已展示给用户跟读）。
        # 关键：前端拉训练文本到用户实际录音提交之间可能间隔数十秒，期间如果
        # 后端再重新拉一次，腾讯云可能返回不同顺序的池子，导致提交的 TextId
        # 对应的"对照文本"跟前端展示给用户的文本不一致，全部被判定漏读。
        # 因此：前端必须把展示时拿到的 TextId 一起传给后端，后端严格用它。
        if not text_id:
            try:
                text_id, _text_content = get_training_text_pair()
            except Exception as e:
                raise RuntimeError(f"获取 VRS 训练文本失败：{e}")
        logger.info("[voice-clone] 一句话复刻模式，使用 TextId=%s 进行音频检测", text_id)
    else:
        logger.info("[voice-clone] 基础版模式，直接进行音质检测（无需训练文本）")

    # 1) 音频质量检测 -> AudioId（两种模式都需要 AudioId 才能 CreateVRSTask）
    det_req = models.DetectEnvAndSoundQualityRequest()
    det_req.AudioData = audio_b64
    det_req.Codec = codec
    det_req.SampleRate = 16000
    det_req.TaskType = task_type
    if is_oneshot and text_id:
        det_req.TextId = text_id
    det_req.TypeId = VRS_TYPE_ID_QUALITY
    try:
        det_resp = client.DetectEnvAndSoundQuality(det_req)
    except TencentCloudSDKException as e:
        raise RuntimeError(f"音频检测失败：{e.code} {e.message}")

    det_full = json.loads(det_resp.to_json_string())
    det_data = det_full.get("Data") or {}
    # 兼容不同字段名：AudioId / AudioIds(数组首元素) / AudioIdList
    audio_id = det_data.get("AudioId") or ""
    if not audio_id:
        for key in ("AudioIds", "AudioIdList", "AudioIdLists"):
            v = det_data.get(key)
            if isinstance(v, list) and v:
                audio_id = v[0]
                break
            if isinstance(v, str) and v:
                audio_id = v
                break
    # 检测通过（DetectionCode=0/Success）且 TypeId=2 会返回 AudioId。
    det_code = det_data.get("DetectionCode")
    det_msg = (det_data.get("DetectionMsg") or "").lower()
    det_passed = det_code in (0, "0", None) or "success" in det_msg or det_msg == "ok"

    if not det_passed:
        logger.warning(
            "[vrs] 音频检测未通过。DetectionCode=%s DetectionMsg=%s 完整响应: %s",
            det_code, det_data.get("DetectionMsg"), det_full,
        )
        detail = _format_vrs_detect_detail(det_data)
        raise RuntimeError(f"音频检测未通过，复刻失败：{detail}")

    if not audio_id:
        # 检测通过却没拿到 AudioId：通常是 TypeId 传错（环境检测不返回 AudioId）
        # 或文本不匹配导致未登记样本。把完整响应暴露出来便于定位。
        logger.warning(
            "[vrs] 检测通过但 AudioId 为空。DetectionCode=%s DetectionMsg=%s 完整响应: %s",
            det_code, det_data.get("DetectionMsg"), det_full,
        )
        detail = _format_vrs_detect_detail(det_data)
        raise RuntimeError(f"音频检测已通过但未返回 AudioId，复刻失败：{detail}")

    # 2) 创建复刻任务
    session_id = uuid.uuid4().hex
    create_req = models.CreateVRSTaskRequest()
    create_req.SessionId = session_id
    create_req.VoiceName = name
    create_req.VoiceGender = voice_gender
    create_req.VoiceLanguage = VRS_LANG_ZH
    # 两种模式都需要音频 ID（AudioIdList 是必传项）
    create_req.AudioIdList = [audio_id]
    create_req.Codec = codec
    create_req.SampleRate = 16000
    create_req.TaskType = task_type
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
    """查复刻任务状态；若训练成功则把 VoiceType 和 FastVoiceType 都写回库。

    返回 {status, voice_type, fast_voice_type, error_message, name}
    """
    with SessionLocal() as db:
        rec = db.get(VoiceCloneTask, rec_id)
        if not rec:
            raise RuntimeError("任务不存在")
        # 已成功但 fast_voice_type 没拉到（升级前的老任务）→ 强制重新查一次腾讯云
        need_retry_vrs = (
            rec.status == "succeeded"
            and not (rec.fast_voice_type or "").strip()
            and bool(rec.task_id)
        )
        if rec.status == "succeeded" and not need_retry_vrs:
            return {
                "status": rec.status,
                "voice_type": rec.voice_type,
                "fast_voice_type": rec.fast_voice_type,
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
                "fast_voice_type": rec.fast_voice_type,
                "error_message": f"{e.code} {e.message}",
                "name": rec.name,
            }
        data = json.loads(resp.to_json_string()).get("Data") or {}
        # Status: 1-训练中 2-成功 3-失败（参考 VRS 回调约定）
        status_code = data.get("Status")
        if status_code == 2 or "VoiceType" in data:
            rec.status = "succeeded"
            rec.voice_type = data.get("VoiceType")
            rec.fast_voice_type = data.get("FastVoiceType")
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
            "fast_voice_type": rec.fast_voice_type,
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
                "fast_voice_type": r.fast_voice_type,
                "task_id": r.task_id,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in recs
        ]


def find_voice_clone_by_tag(tag_value: str) -> Optional[dict]:
    """用字符串查找命中的复刻任务。tag 可为 fast_voice_type 字符串或 voice_type 整数（转为字符串）。"""
    if not tag_value:
        return None
    with SessionLocal() as db:
        rec = db.query(VoiceCloneTask).filter(
            VoiceCloneTask.status == "succeeded",
            VoiceCloneTask.fast_voice_type == tag_value,
        ).order_by(VoiceCloneTask.id.desc()).first()
        if rec is not None:
            return {
                "rec": rec,
                "match_key": "fast_voice_type",
                "voice_type": rec.voice_type,
                "fast_voice_type": rec.fast_voice_type,
            }
        try:
            vt_int = int(str(tag_value))
        except (TypeError, ValueError):
            vt_int = None
        if vt_int is not None:
            rec = db.query(VoiceCloneTask).filter(
                VoiceCloneTask.status == "succeeded",
                VoiceCloneTask.voice_type == vt_int,
            ).order_by(VoiceCloneTask.id.desc()).first()
            if rec is not None:
                return {
                    "rec": rec,
                    "match_key": "voice_type",
                    "voice_type": rec.voice_type,
                    "fast_voice_type": rec.fast_voice_type,
                }
        return None
