from app.adapters.base import TextGenerateInput, TextGenerateResult


class StubTextAdapter:
    provider = "stub"

    async def generate(self, data: TextGenerateInput) -> TextGenerateResult:
        title = f"{data.topic[:18]}..." if len(data.topic) > 18 else data.topic
        return TextGenerateResult(
            title=title,
            content=f"【{data.platform}】{data.topic}\n\n这是一段 stub 文案，用于无 API Key 时的本地联调。",
            tags=["AI发布", data.platform, "测试"],
            cover_text=data.topic[:12],
            comment_guide=f"欢迎聊聊你对{data.topic[:8]}的看法～",
            provider=self.provider,
            prompt=data.topic,
            cost=0.0,
        )
