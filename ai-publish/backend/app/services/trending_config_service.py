from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.system_config_service import SystemConfigService

TRENDING_PLATFORMS = ("douyin", "bilibili")

LEGACY_MINI_GAME_KEYWORDS = "小游戏,手游,休闲游戏,试玩"
DEFAULT_MINI_GAME_KEYWORDS = (
    "小游戏,手游,休闲游戏,试玩,游戏,"
    "原神,鸣潮,崩坏,星穹铁道,绝区零,王者荣耀,和平精英,蛋仔派对,元梦之星,"
    "英雄联盟,阴阳师,明日方舟,第五人格,光遇,逆水寒,梦幻西游,金铲铲,云顶之弈,"
    "吃鸡,PUBG,CS2,迷你世界,我的世界"
)


class TrendingConfigService:
    def __init__(self, db: Session) -> None:
        self.config = SystemConfigService(db)

    def enabled(self) -> bool:
        return self.config.get_bool("trending_enabled", False)

    def fetch_mode(self) -> str:
        raw = (self.config.get_value("trending_fetch_mode") or "auto").strip().lower()
        if raw in {"server", "local_worker", "auto"}:
            return raw
        return "auto"

    def fetch_cron_hour(self) -> int:
        return max(0, min(23, self.config.get_int("trending_fetch_cron_hour", 8)))

    def dailyhot_base_url(self) -> str:
        return (self.config.get_value("trending_dailyhot_base_url") or "https://api-hot.imsyy.top").strip()

    def mini_game_keywords(self) -> list[str]:
        raw = self.config.get_value("trending_mini_game_keywords") or DEFAULT_MINI_GAME_KEYWORDS
        return [item.strip() for item in raw.split(",") if item.strip()]

    def matches_mini_game(self, title: str, tags: list[str] | None = None) -> bool:
        keywords = [kw.lower() for kw in self.mini_game_keywords()]
        if not keywords:
            return False
        haystack = " ".join([title or "", " ".join(tags or [])]).lower()
        return any(keyword in haystack for keyword in keywords)

    def paid_api_enabled(self) -> bool:
        return self.config.get_bool("trending_paid_api_enabled", False)

    def paid_provider(self) -> str:
        raw = (self.config.get_value("trending_paid_provider") or "tikhub").strip().lower()
        return raw if raw in {"tikhub"} else "tikhub"

    def paid_api_key(self) -> str:
        return (self.config.get_value("trending_paid_api_key") or "").strip()
