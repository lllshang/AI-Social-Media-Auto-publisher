"""Stub 数字人视频适配器 — 占位，待接入真实 provider。"""

import uuid
from pathlib import Path

import cv2
import numpy as np

from app.adapters.base import VideoGenerateInput, VideoGenerateResult


class DigitalHumanStubVideoAdapter:
    """占位数字人视频生成器（返回 1 秒黑屏视频，附带 avatar 信息标记）"""

    provider = "digital_human_stub"

    async def generate(self, data: VideoGenerateInput) -> VideoGenerateResult:
        from app.adapters.factory import get_adapter_factory

        storage = get_adapter_factory().get_storage_adapter()

        width, height = 1280, 720
        fps = 24
        frames = fps  # 1 秒

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        temp_path = Path("/tmp") / f"stub_dh_{uuid.uuid4().hex}.mp4"

        out = cv2.VideoWriter(str(temp_path), fourcc, fps, (width, height))
        black_frame = np.zeros((height, width, 3), dtype=np.uint8)

        for _ in range(frames):
            out.write(black_frame)
        out.release()

        video_path, _ = storage.save_file(str(temp_path), suffix=".mp4")
        temp_path.unlink()

        thumbnail_bytes = cv2.imencode(".jpg", black_frame)[1].tobytes()
        thumbnail_path, _ = storage.save_bytes(thumbnail_bytes, suffix=".jpg")

        return VideoGenerateResult(
            video_paths=[video_path],
            thumbnail_paths=[thumbnail_path],
            provider=self.provider,
            prompt=data.topic,
            cost=0.0,
            duration=1.0,
            metadata={
                "avatar_id": data.avatar_id,
                "avatar_type": data.avatar_type,
                "note": "stub placeholder - real provider TBD",
            },
        )
