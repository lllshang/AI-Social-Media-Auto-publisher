from __future__ import annotations

import re

import httpx
from loguru import logger

from app.adapters.trending.base import TrendingRawItem, TrendingSourceAdapter

PLATFORM_PATHS = {
    "douyin": "douyin",
    "bilibili": "bilibili",
}


def _parse_heat(value: object) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if not text:
        return 0.0
    multiplier = 1.0
    if text.endswith("万"):
        multiplier = 10000.0
        text = text[:-1]
    elif text.endswith("亿"):
        multiplier = 100000000.0
        text = text[:-1]
    match = re.search(r"[\d.]+", text)
    if not match:
        return 0.0
    try:
        return float(match.group()) * multiplier
    except ValueError:
        return 0.0


class FreeDailyHotAdapter(TrendingSourceAdapter):
    source_name = "dailyhot"

    def __init__(self, base_url: str) -> None:
        self.base_url = (base_url or "https://api-hot.imsyy.top").rstrip("/")

    async def fetch_platform(self, platform: str) -> list[TrendingRawItem]:
        path = PLATFORM_PATHS.get(platform)
        if not path:
            return []
        url = f"{self.base_url}/{path}"
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            payload = response.json()

        rows = payload.get("data") if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            logger.warning("DailyHot 返回格式异常 platform={} payload={}", platform, str(payload)[:200])
            return []

        items: list[TrendingRawItem] = []
        for index, row in enumerate(rows, start=1):
            if not isinstance(row, dict):
                continue
            title = (row.get("title") or row.get("name") or row.get("word") or "").strip()
            if not title:
                continue
            heat = _parse_heat(row.get("hot") or row.get("heat") or row.get("hot_value") or row.get("index"))
            tags = []
            for key in ("label", "category", "desc"):
                value = row.get(key)
                if value and isinstance(value, str):
                    tags.append(value.strip())
            items.append(
                TrendingRawItem(
                    platform=platform,
                    rank=index,
                    title=title,
                    heat_score=heat or float(max(1, 100 - index)),
                    source_url=row.get("url") or row.get("mobileUrl") or row.get("link"),
                    cover_url=row.get("cover") or row.get("pic") or row.get("thumbnail"),
                    video_url=row.get("video_url") or row.get("video"),
                    tags=tags,
                )
            )
        return items
