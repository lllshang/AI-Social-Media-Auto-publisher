from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TrendingRawItem:
    platform: str
    rank: int
    title: str
    heat_score: float = 0.0
    source_url: str | None = None
    cover_url: str | None = None
    video_url: str | None = None
    tags: list[str] = field(default_factory=list)


class TrendingSourceAdapter:
    source_name = "unknown"

    async def fetch_platform(self, platform: str) -> list[TrendingRawItem]:
        raise NotImplementedError
