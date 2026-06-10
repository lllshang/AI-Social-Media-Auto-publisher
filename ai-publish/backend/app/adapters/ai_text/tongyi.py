import json

import httpx

from app.adapters.base import TextGenerateInput, TextGenerateResult
from app.config import get_settings
from app.utils.prompt_templates import load_prompt_template


class TongyiTextAdapter:
    provider = "tongyi"

    def __init__(self, model: str = "qwen-plus") -> None:
        self.settings = get_settings()
        self.model = model

    async def generate(self, data: TextGenerateInput) -> TextGenerateResult:
        template = load_prompt_template("text", data.platform, content_type=data.content_type)
        prompt = (
            template.replace("{platform}", data.platform)
            .replace("{topic}", data.topic)
            .replace("{style}", data.style)
        )
        from app.services.ai_provider_config_service import AiProviderConfigService

        api_key = AiProviderConfigService().get_field_value("dashscope_api_key")
        if not api_key:
            from app.adapters.ai_text.stub import StubTextAdapter

            result = await StubTextAdapter().generate(data)
            result.provider = self.provider
            result.prompt = prompt
            return result

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model,
            "input": {"messages": [{"role": "user", "content": prompt}]},
            "parameters": {"result_format": "message"},
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation",
                headers=headers,
                json=body,
            )
            resp.raise_for_status()
            payload = resp.json()

        content = payload["output"]["choices"][0]["message"]["content"]
        parsed = self._parse_content(content, data.topic)
        usage = payload.get("usage", {})
        cost = float(usage.get("total_tokens", 0))
        return TextGenerateResult(
            title=parsed["title"],
            content=parsed["content"],
            tags=parsed["tags"],
            cover_text=parsed["cover_text"],
            comment_guide=parsed["comment_guide"],
            provider=self.provider,
            prompt=prompt,
            cost=cost,
        )

    def _parse_content(self, content: str, topic: str) -> dict:
        try:
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(content[start:end])
                return {
                    "title": data.get("title", topic[:20]),
                    "content": data.get("content", content),
                    "tags": data.get("tags", ["小红书"]),
                    "cover_text": data.get("cover_text", topic[:12]),
                    "comment_guide": data.get("comment_guide", f"你对{topic[:8]}怎么看？"),
                }
        except json.JSONDecodeError:
            pass
        return {
            "title": topic[:20],
            "content": content,
            "tags": ["小红书", "AI"],
            "cover_text": topic[:12],
            "comment_guide": f"你对{topic[:8]}怎么看？",
        }
