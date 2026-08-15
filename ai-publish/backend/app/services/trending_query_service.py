from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import TrendingItem
from app.services.trending_config_service import TrendingConfigService


class TrendingQueryService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.config = TrendingConfigService(db)

    def list_items(
        self,
        *,
        period: str = "daily",
        platform: str | None = None,
        category: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        today = date.today()
        if period == "daily":
            start_date = today.isoformat()
            end_date = start_date
        elif period == "rolling_7d":
            start_date = (today - timedelta(days=6)).isoformat()
            end_date = today.isoformat()
        elif period == "rolling_30d":
            start_date = (today - timedelta(days=29)).isoformat()
            end_date = today.isoformat()
        else:
            start_date = today.isoformat()
            end_date = start_date

        query = self.db.query(TrendingItem).filter(
            TrendingItem.snapshot_date >= start_date,
            TrendingItem.snapshot_date <= end_date,
        )
        if platform:
            query = query.filter(TrendingItem.platform == platform)

        rows = query.all()
        if period == "daily":
            aggregated = self._aggregate_daily(rows)
        else:
            aggregated = self._aggregate_rolling(rows)

        if category == "mini_game":
            keywords = [kw.lower() for kw in self.config.mini_game_keywords()]
            aggregated = [
                item
                for item in aggregated
                if self._match_mini_game(item, keywords)
            ]

        aggregated.sort(key=lambda item: item["heat_score"], reverse=True)
        return aggregated[: max(1, min(limit, 200))]

    def get_item(self, item_id: int) -> TrendingItem | None:
        return self.db.query(TrendingItem).filter(TrendingItem.id == item_id).first()

    def _aggregate_daily(self, rows: list[TrendingItem]) -> list[dict]:
        result: list[dict] = []
        for row in rows:
            result.append(self._to_dict(row, appear_days=1))
        result.sort(key=lambda item: (item.get("rank") or 9999))
        return result

    def _aggregate_rolling(self, rows: list[TrendingItem]) -> list[dict]:
        buckets: dict[tuple[str, str], dict] = {}
        for row in rows:
            key = (row.platform, row.title)
            if key not in buckets:
                buckets[key] = {
                    "platform": row.platform,
                    "title": row.title,
                    "tags": row.tags or [],
                    "source_url": row.source_url,
                    "cover_url": row.cover_url,
                    "video_url": row.video_url,
                    "heat_score": 0.0,
                    "best_rank": row.rank or 9999,
                    "appear_days": 0,
                    "first_seen_at": row.first_seen_at,
                    "last_seen_at": row.last_seen_at,
                    "ids": [],
                }
            bucket = buckets[key]
            rank = row.rank or 9999
            weight = max(1.0, 101 - min(rank, 100))
            bucket["heat_score"] += float(row.heat_score or 0) + weight
            bucket["best_rank"] = min(bucket["best_rank"], rank)
            bucket["appear_days"] += 1
            bucket["ids"].append(row.id)
            if row.last_seen_at and (not bucket["last_seen_at"] or row.last_seen_at > bucket["last_seen_at"]):
                bucket["last_seen_at"] = row.last_seen_at
                bucket["source_url"] = row.source_url or bucket["source_url"]
                bucket["cover_url"] = row.cover_url or bucket["cover_url"]
        result = []
        for bucket in buckets.values():
            result.append(
                {
                    "id": bucket["ids"][-1],
                    "platform": bucket["platform"],
                    "title": bucket["title"],
                    "tags": bucket["tags"],
                    "source_url": bucket["source_url"],
                    "cover_url": bucket["cover_url"],
                    "video_url": bucket["video_url"],
                    "heat_score": round(bucket["heat_score"], 2),
                    "rank": bucket["best_rank"],
                    "appear_days": bucket["appear_days"],
                    "first_seen_at": bucket["first_seen_at"],
                    "last_seen_at": bucket["last_seen_at"],
                }
            )
        return result

    def _to_dict(self, row: TrendingItem, *, appear_days: int) -> dict:
        return {
            "id": row.id,
            "platform": row.platform,
            "title": row.title,
            "tags": row.tags or [],
            "source_url": row.source_url,
            "cover_url": row.cover_url,
            "video_url": row.video_url,
            "heat_score": float(row.heat_score or 0),
            "rank": row.rank,
            "appear_days": appear_days,
            "first_seen_at": row.first_seen_at,
            "last_seen_at": row.last_seen_at,
            "snapshot_date": row.snapshot_date,
        }

    @staticmethod
    def _match_mini_game(item: dict, keywords: list[str]) -> bool:
        if not keywords:
            return True
        haystack = " ".join(
            [
                item.get("title") or "",
                " ".join(item.get("tags") or []),
            ]
        ).lower()
        return any(keyword in haystack for keyword in keywords)

    def status(self) -> dict:
        latest = (
            self.db.query(func.max(TrendingItem.last_seen_at)).scalar()
        )
        last_run = (
            self.db.query(TrendingItem)
            .order_by(TrendingItem.created_at.desc())
            .first()
        )
        from app.services.trending_fetch_service import TrendingFetchService

        run = TrendingFetchService(self.db).latest_success_run()
        return {
            "enabled": self.config.enabled(),
            "fetch_mode": self.config.fetch_mode(),
            "paid_api_enabled": self.config.paid_api_enabled(),
            "last_item_at": latest.isoformat() if latest else None,
            "last_fetch_at": run.finished_at.isoformat() if run and run.finished_at else None,
            "last_fetch_source": run.source if run else None,
            "last_fetch_status": run.status if run else None,
            "stale": bool(last_run and run and run.finished_at and latest and latest < run.finished_at),
        }
