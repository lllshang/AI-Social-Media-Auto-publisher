"""声音复刻（VRS）相关接口。

- POST /api/voice-clone           上传样本音频，创建复刻任务
- GET  /api/voice-clone           列出我的复刻音色（含训练状态）
- GET  /api/voice-clone/training-text  获取 VRS 标准训练文本（引导录制）
- GET  /api/voice-clone/{task_id}/status  查询某条任务训练状态
"""

from __future__ import annotations

import os

from fastapi import APIRouter, UploadFile, File, Form, HTTPException

from app.services import voice_clone_service as svc

router = APIRouter(prefix="/api/voice-clone", tags=["voice-clone"])

# 允许上传的音频格式
_ALLOWED_EXT = {".wav", ".mp3", ".m4a", ".aac"}


@router.get("/training-text")
def training_text():
    """获取 VRS 标准训练文本，前端可展示引导用户录制。

    基础版（TaskType=1）不需要训练文本，返回空列表 + mode 标记；
    一句话复刻（TaskType=5）返回训练文本列表。
    """
    try:
        mode = svc.get_current_task_type()
        if mode == svc.VRS_TASK_TYPE_ONESHOT:
            return {"mode": "oneshot", "items": svc.get_training_text()}
        return {"mode": "basic", "items": []}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"获取训练文本失败：{e}")


@router.post("")
async def create_clone(
    name: str = Form(...),
    voice_gender: int = Form(1),
    audio: UploadFile = File(...),
    text_id: str | None = Form(None),  # 仅一句话复刻（TaskType=5）需要：前端展示的训练文本对应的 TextId
    task_type: int | None = Form(None),  # 复刻模式：1=基础版(默认) 5=一句话复刻(充值后切)
):
    """上传样本音频，创建声音复刻任务。

    - name: 复刻音色命名
    - voice_gender: 1-男 2-女
    - audio: wav/mp3/m4a/aac，建议 10s 左右清晰单人录音
    - text_id: 仅一句话复刻模式需要（前端展示的训练文本对应的 TextId）
    - task_type: 复刻模式；不传则读配置表默认（基础版）
    """
    from loguru import logger
    logger.info(
        f"[voice-clone POST] name={name!r} gender={voice_gender} task_type={task_type!r} text_id={text_id!r} "
        f"audio.filename={audio.filename!r} audio.content_type={audio.content_type!r}"
    )
    ext = os.path.splitext(audio.filename or "")[1].lower()
    if ext not in _ALLOWED_EXT:
        raise HTTPException(status_code=400, detail=f"不支持的音频格式：{ext}，仅支持 wav/mp3/m4a/aac")

    # 暂存到临时文件
    import tempfile
    tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
    try:
        content = await audio.read()
        if not content:
            raise HTTPException(status_code=400, detail="音频文件为空")
        tmp.write(content)
        tmp.close()
        rec = svc.create_clone_task(
            name=name, audio_path=tmp.name, voice_gender=voice_gender,
            text_id=text_id, task_type=task_type,
        )
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        from loguru import logger
        logger.exception(f"[voice-clone POST] 复刻失败 name={name!r} ext={ext!r} size={len(content) if 'content' in locals() else 0}: {e}")
        raise HTTPException(status_code=502, detail=f"复刻任务创建失败：{e}")
    finally:
        # 清理原始上传临时文件 + 裁剪后可能产生的 .trimmed.* 文件
        for p in (tmp.name, tmp.name + ".trimmed.wav"):
            try:
                os.unlink(p)
            except FileNotFoundError:
                pass
            except Exception:
                pass

    return {
        "id": rec.id,
        "name": rec.name,
        "status": rec.status,
        "task_id": rec.task_id,
    }


@router.get("")
def list_voices():
    """列出我的复刻音色。"""
    return {"items": svc.list_my_voices()}


@router.get("/{task_id}/status")
def task_status(task_id: int):
    """查询某条复刻任务的训练状态；成功时返回 voice_type。"""
    try:
        return svc.query_task_status(task_id)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=404, detail=str(e))
