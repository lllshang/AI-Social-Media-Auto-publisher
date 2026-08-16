from __future__ import annotations

import httpx
from loguru import logger

from app.adapters.trending.base import TrendingRawItem, TrendingSourceAdapter

# TikHub 热榜端点可能随版本调整；失败时由上层降级到缓存。
TIKHUB_HOT_ENDPOINTS = {
    "douyin": "https://api.tikhub.io/api/v1/douyin/billboard/fetch_hot_search_result",
    "bilibili": "https://api.tikhub.io/api/v1/bilibili/web/fetch_popular_videos",
}


class PaidTikHubAdapter(TrendingSourceAdapter):
    source_name = "tikhub"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key.strip()

    async def fetch_platform(self, platform: str) -> list[TrendingRawItem]:
        if not self.api_key:
            return []
        endpoint = TIKHUB_HOT_ENDPOINTS.get(platform)
        if not endpoint:
            return []
        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(endpoint, headers=headers)
            response.raise_for_status()
            payload = response.json()

        data = payload.get("data") if isinstance(payload, dict) else payload
        rows: list = []
        if isinstance(data, dict):
            for key in ("list", "items", "word_list", "data"):
                candidate = data.get(key)
                if isinstance(candidate, list):
                    rows = candidate
                    break
        elif isinstance(data, list):
            rows = data

        items: list[TrendingRawItem] = []
        for index, row in enumerate(rows, start=1):
            if not isinstance(row, dict):
                continue
            title = (
                row.get("word")
                or row.get("title")
                or row.get("keyword")
                or row.get("name")
                or ""
            ).strip()
            if not title:
                continue
            heat = float(row.get("hot_value") or row.get("heat") or row.get("view") or max(1, 100 - index))
            items.append(
                TrendingRawItem(
                    platform=platform,
                    rank=index,
                    title=title,
                    heat_score=heat,
                    source_url=row.get("url") or row.get("link"),
                    cover_url=row.get("cover") or row.get("pic"),
                    video_url=row.get("video_url"),
                    tags=[],
                )
            )
        if not items:
            logger.warning("TikHub 热榜解析为空 platform={}", platform)
        return items
