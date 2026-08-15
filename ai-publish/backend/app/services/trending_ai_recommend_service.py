from __future__ import annotations

import json
from pathlib import Path

import httpx
import yaml
from sqlalchemy.orm import Session

from app.adapters.ai_text.openai_compatible import AiProviderError
from app.services.ai_model_service import AiModelService
from app.services.trending_query_service import TrendingQueryService


def _load_trending_recommend_template() -> str:
    path = Path(__file__).resolve().parents[1] / "templates" / "prompts" / "trending_recommend.yaml"
    if not path.exists():
        return "根据热点推荐选题，输出 JSON recommendations 数组：{trends_json}"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return str(data.get("template", ""))


class TrendingAiRecommendService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.query = TrendingQueryService(db)
        self.ai = AiModelService()

    async def recommend(
        self,
        *,
        period: str = "daily",
        platform: str | None = None,
        category: str | None = None,
        limit: int = 5,
    ) -> dict:
        trends = self.query.list_items(period=period, platform=platform, category=category, limit=30)
        if not trends:
            return {"recommendations": [], "message": "暂无热点数据，请先执行抓取"}

        adapter = self.ai.get_text_adapter()
        if adapter.__class__.__name__ == "StubTextAdapter":
            raise AiProviderError("文案模型未配置，请在 AI 模型页配置后重试")

        template = _load_trending_recommend_template()
        prompt = template.replace("{trends_json}", json.dumps(trends, ensure_ascii=False, default=str))

        provider = getattr(adapter, "provider", "unknown")
        api_key = getattr(adapter, "api_key", "")
        base_url = getattr(adapter, "base_url", "")
        model = getattr(adapter, "model", "")

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        body = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "你是选题顾问，只输出合法 JSON，包含 recommendations 数组。",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.6,
        }
        url = f"{base_url.rstrip('/')}/chat/completions"
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            payload = resp.json()

        content = (payload.get("choices") or [{}])[0].get("message", {}).get("content") or ""
        recommendations = self._parse_recommendations(content)
        return {"recommendations": recommendations[:limit], "provider": provider}

    @staticmethod
    def _parse_recommendations(content: str) -> list[dict]:
        start = content.find("{")
        end = content.rfind("}") + 1
        if start < 0 or end <= start:
            return []
        try:
            data = json.loads(content[start:end])
        except json.JSONDecodeError:
            return []
        rows = data.get("recommendations")
        if not isinstance(rows, list):
            return []
        result = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            topic = (row.get("topic") or "").strip()
            if not topic:
                continue
            platform = row.get("platform") or "douyin"
            if platform not in {"douyin", "bilibili"}:
                platform = "douyin"
            result.append(
                {
                    "topic": topic,
                    "platform": platform,
                    "content_type": "video",
                    "reason": row.get("reason") or "",
                    "reference_trend_ids": row.get("reference_trend_ids") or [],
                }
            )
        return result
