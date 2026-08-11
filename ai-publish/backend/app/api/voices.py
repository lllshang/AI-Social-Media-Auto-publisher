"""
数字人口播音色 API

- GET  /api/voices          标准音色清单（edge-tts 中文/粤语/台普 20+ 个）
- POST /api/voices/preview  输入文本 + 音色 ID → 试听 mp3
"""

from __future__ import annotations

import io

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.utils.tts import (
    DEFAULT_VOICE_ID,
    list_voices,
    synthesize_speech,
)

router = APIRouter()


@router.get("/api/voices")
def get_voices() -> dict:
    """返回标准音色清单（前端下拉用）。"""
    return {
        "default_voice_id": DEFAULT_VOICE_ID,
        "voices": list_voices(),
    }


class VoicePreviewRequest(BaseModel):
    text: str
    voice_id: str | None = None
    rate: str = "+0%"
    volume: str = "+0%"


@router.post("/api/voices/preview")
def preview_voice(req: VoicePreviewRequest) -> StreamingResponse:
    """实时合成试听片段，浏览器直接播放。

    对复刻音色（voice_id = "clone:<tag>"）会从复刻库中找出对应的 fast_voice_type
    并同步传给 TTS，避免腾讯云 TTS 报"check FastVoiceType"。
    """
    voice_id = req.voice_id
    fast_voice_type = None
    voice_type_int = None
    if voice_id and voice_id.startswith("clone:"):
        tag = voice_id[len("clone:"):]
        try:
            from app.services.voice_clone_service import find_voice_clone_by_tag
            hit = find_voice_clone_by_tag(tag)
            if hit:
                fast_voice_type = hit.get("fast_voice_type")
                voice_type_int = hit.get("voice_type")
        except Exception:
            # 查不到不影响标准路径，回退走整数 voice_type
            pass

    try:
        result = synthesize_speech(
            text=req.text,
            voice_id=voice_id,
            voice_type=voice_type_int,
            fast_voice_type=fast_voice_type,
            rate=req.rate,
            volume=req.volume,
            prefix="preview",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"试听合成失败：{e}") from e

    with open(result.audio_path, "rb") as f:
        buf = io.BytesIO(f.read())
    return StreamingResponse(
        buf,
        media_type="audio/mpeg",
        headers={"Content-Disposition": f'inline; filename="{result.voice_id}.mp3"'},
    )
