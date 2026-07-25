from app.adapters.base import VideoGenerateInput, VideoGenerateResult


class HunyuanVideoAdapter:
    """腾讯混元视频生成适配器（占位，待官方 API）"""

    provider = "hunyuan_video"

    async def generate(self, data: VideoGenerateInput) -> VideoGenerateResult:
        # 当前混元视频 API 未公开，降级到 Stub
        from app.adapters.ai_video.stub import StubVideoAdapter

        result = await StubVideoAdapter().generate(data)
        result.provider = self.provider
        return result
