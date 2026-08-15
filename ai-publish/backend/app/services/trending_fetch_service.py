from __future__ import annotations

from datetime import date, datetime

from loguru import logger
from sqlalchemy.orm import Session

from app.adapters.trending.base import TrendingRawItem
from app.adapters.trending.dailyhot import FreeDailyHotAdapter
from app.adapters.trending.tikhub import PaidTikHubAdapter
from app.adapters.trending.xxapi import XxApiFallbackAdapter
from app.models import TrendingFetchRun, TrendingItem
from app.services.trending_config_service import TRENDING_PLATFORMS, TrendingConfigService


class TrendingFetchService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.config = TrendingConfigService(db)

    async def fetch_all(self, *, mode_override: str | None = None) -> TrendingFetchRun:
        if not self.config.enabled():
            raise ValueError("热点抓取未启用，请在系统设置中开启 trending_enabled")

        mode = mode_override or self.config.fetch_mode()
        run = TrendingFetchRun(source="pending", mode=mode, status="running", started_at=datetime.utcnow())
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)

        errors: list[str] = []
        total = 0
        source = "dailyhot"
        snapshot_date = date.today().isoformat()

        try:
            if mode == "local_worker":
                # 第一期：本机 Worker 通过相同 HTTP 源抓取后 ingest；调度侧先走 server 免费源兜底。
                raw_items, source, errors = await self._fetch_with_fallback()
            else:
                raw_items, source, errors = await self._fetch_with_fallback()

            total = self._persist_items(raw_items, snapshot_date=snapshot_date)
            run.source = source
            run.item_count = total
            run.status = "success" if total else ("partial" if errors else "failed")
            if errors and total:
                run.error_message = "; ".join(errors)[:2000]
            elif errors:
                run.error_message = "; ".join(errors)[:2000]
                run.status = "failed"
        except Exception as exc:
            logger.exception("热点抓取失败: {}", exc)
            run.status = "failed"
            run.error_message = str(exc)
        finally:
            run.finished_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(run)
        return run

    async def ingest_raw_items(
        self,
        items: list[TrendingRawItem],
        *,
        source: str = "local_worker",
        mode: str = "local_worker",
    ) -> TrendingFetchRun:
        run = TrendingFetchRun(source=source, mode=mode, status="running", started_at=datetime.utcnow())
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        try:
            count = self._persist_items(items, snapshot_date=date.today().isoformat())
            run.item_count = count
            run.status = "success" if count else "failed"
        except Exception as exc:
            run.status = "failed"
            run.error_message = str(exc)
        finally:
            run.finished_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(run)
        return run

    async def _fetch_with_fallback(self) -> tuple[list[TrendingRawItem], str, list[str]]:
        errors: list[str] = []
        raw_items: list[TrendingRawItem] = []
        sources_used: set[str] = set()

        dailyhot = FreeDailyHotAdapter(self.config.dailyhot_base_url())
        xxapi = XxApiFallbackAdapter()

        for platform in TRENDING_PLATFORMS:
            rows: list[TrendingRawItem] = []
            try:
                rows = await dailyhot.fetch_platform(platform)
                if rows:
                    sources_used.add("dailyhot")
            except Exception as exc:
                errors.append(f"{platform}:dailyhot:{exc}")

            if not rows:
                try:
                    rows = await xxapi.fetch_platform(platform)
                    if rows:
                        sources_used.add("xxapi")
                except Exception as exc:
                    errors.append(f"{platform}:xxapi:{exc}")

            raw_items.extend(rows)

        source = "+".join(sorted(sources_used)) if sources_used else "dailyhot"

        if not raw_items and self.config.paid_api_enabled():
            paid_key = self.config.paid_api_key()
            if paid_key:
                paid = PaidTikHubAdapter(paid_key)
                source = "tikhub"
                for platform in TRENDING_PLATFORMS:
                    try:
                        rows = await paid.fetch_platform(platform)
                        raw_items.extend(rows)
                    except Exception as exc:
                        errors.append(f"{platform}:tikhub:{exc}")
            else:
                errors.append("paid:missing_api_key")

        return raw_items, source, errors

    def _persist_items(self, raw_items: list[TrendingRawItem], *, snapshot_date: str) -> int:
        now = datetime.utcnow()
        count = 0
        for raw in raw_items:
            title = raw.title.strip()
            if not title:
                continue
            tags = list(raw.tags or [])
            if self.config.matches_mini_game(title, tags) and "小游戏" not in tags:
                tags.insert(0, "小游戏")
            existing = (
                self.db.query(TrendingItem)
                .filter(
                    TrendingItem.platform == raw.platform,
                    TrendingItem.snapshot_date == snapshot_date,
                    TrendingItem.title == title,
                )
                .first()
            )
            if existing:
                existing.rank = raw.rank
                existing.heat_score = raw.heat_score
                existing.source_url = raw.source_url
                existing.cover_url = raw.cover_url
                existing.video_url = raw.video_url
                existing.tags = tags
                existing.last_seen_at = now
            else:
                self.db.add(
                    TrendingItem(
                        platform=raw.platform,
                        snapshot_date=snapshot_date,
                        rank=raw.rank,
                        title=title,
                        tags=tags,
                        heat_score=raw.heat_score,
                        source_url=raw.source_url,
                        cover_url=raw.cover_url,
                        video_url=raw.video_url,
                        first_seen_at=now,
                        last_seen_at=now,
                    )
                )
            count += 1
        self.db.commit()
        return count

    def latest_success_run(self) -> TrendingFetchRun | None:
        return (
            self.db.query(TrendingFetchRun)
            .filter(TrendingFetchRun.status.in_(["success", "partial"]))
            .order_by(TrendingFetchRun.finished_at.desc())
            .first()
        )
