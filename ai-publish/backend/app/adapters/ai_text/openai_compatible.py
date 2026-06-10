import json
from pathlib import Path

import httpx
import yaml

from app.adapters.base import TextGenerateInput, TextGenerateResult


class AiProviderError(RuntimeError):
    """AI 厂商调用失败，携带可读说明。"""


class OpenAiCompatibleTextAdapter:
    """OpenAI Chat Completions 兼容接口：OpenAI / DeepSeek / Moonshot / 腾讯混元 / Ollama 等。"""

    def __init__(
        self,
        *,
        provider: str,
        api_key: str,
        base_url: str,
        model: str,
    ) -> None:
        self.provider = provider
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.prompt_template = self._load_template()

    def _load_template(self) -> str:
        template_path = Path(__file__).resolve().parents[2] / "templates" / "prompts" / "xhs_text.yaml"
        if template_path.exists():
            data = yaml.safe_load(template_path.read_text(encoding="utf-8"))
            return data.get("template", "")
        return "请为{platform}平台围绕主题「{topic}」生成标题、正文、标签和封面文案，以JSON返回。"

    async def generate(self, data: TextGenerateInput) -> TextGenerateResult:
        if not self.api_key or self.api_key in {"ollama", ""}:
            if self.provider != "ollama":
                raise AiProviderError(
                    f"{self.provider} 未配置 API Key，请在「AI 模型 → 厂商 API Key 配置」中保存 Key 后重试"
                )

        prompt = (
            self.prompt_template.replace("{platform}", data.platform)
            .replace("{topic}", data.topic)
            .replace("{style}", data.style)
        )
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        body = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "你是社交媒体内容创作助手，输出必须是合法 JSON，包含 title、content、tags、cover_text、comment_guide 字段。",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
        }
        if self.provider == "hunyuan":
            body["response_format"] = {"type": "json_object"}

        url = f"{self.base_url}/chat/completions"
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(url, headers=headers, json=body)
                resp.raise_for_status()
                payload = resp.json()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:500]
            try:
                err_json = exc.response.json()
                detail = err_json.get("error", {}).get("message") or err_json.get("message") or detail
            except Exception:
                pass
            raise AiProviderError(
                f"{self.provider} API 调用失败 (HTTP {exc.response.status_code}): {detail}"
            ) from exc
        except httpx.RequestError as exc:
            raise AiProviderError(f"{self.provider} 网络请求失败: {exc}") from exc

        choices = payload.get("choices") or []
        if not choices:
            raise AiProviderError(f"{self.provider} 返回空结果: {str(payload)[:300]}")

        content = choices[0].get("message", {}).get("content") or ""
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
