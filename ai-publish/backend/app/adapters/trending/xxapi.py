from __future__ import annotations

import httpx
from loguru import logger

from app.adapters.trending.base import TrendingRawItem, TrendingSourceAdapter
from app.adapters.trending.dailyhot import _parse_heat

XXAPI_BASE = "https://v2.xxapi.cn/api"

PLATFORM_ENDPOINTS = {
    "douyin": "douyinhot",
    "bilibili": "bilibilihot",
}


class XxApiFallbackAdapter(TrendingSourceAdapter):
    """免费热榜兜底源（当 DailyHot 不可达时使用）。"""

    source_name = "xxapi"

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or XXAPI_BASE).rstrip("/")

    async def fetch_platform(self, platform: str) -> list[TrendingRawItem]:
        endpoint = PLATFORM_ENDPOINTS.get(platform)
        if not endpoint:
            return []

        url = f"{self.base_url}/{endpoint}"
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            payload = response.json()

        if not isinstance(payload, dict):
            logger.warning("xxapi 返回格式异常 platform={} payload={}", platform, str(payload)[:200])
            return []
        if payload.get("code") not in (200, "200", None):
            raise RuntimeError(payload.get("msg") or f"xxapi code={payload.get('code')}")

        rows = payload.get("data")
        if not isinstance(rows, list) or not rows:
            return []

        items: list[TrendingRawItem] = []
        for index, row in enumerate(rows, start=1):
            if isinstance(row, str):
                title = row.strip()
                if not title:
                    continue
                items.append(
                    TrendingRawItem(
                        platform=platform,
                        rank=index,
                        title=title,
                        heat_score=float(max(1, 100 - index)),
                    )
                )
                continue
            if not isinstance(row, dict):
                continue
            title = (row.get("title") or row.get("name") or row.get("word") or "").strip()
            if not title:
                continue
            heat = _parse_heat(row.get("hot_value") or row.get("hot") or row.get("heat") or row.get("index"))
            cover = None
            word_cover = row.get("word_cover")
            if isinstance(word_cover, dict):
                urls = word_cover.get("url_list")
                if isinstance(urls, list) and urls:
                    cover = urls[0]
            items.append(
                TrendingRawItem(
                    platform=platform,
                    rank=index,
                    title=title,
                    heat_score=heat or float(max(1, 100 - index)),
                    source_url=row.get("url") or row.get("mobileUrl") or row.get("link"),
                    cover_url=cover or row.get("cover") or row.get("pic"),
                    video_url=row.get("video_url") or row.get("video"),
                    tags=[],
                )
            )
        return items
