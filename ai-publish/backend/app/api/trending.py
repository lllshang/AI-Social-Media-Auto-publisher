from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.adapters.ai_text.openai_compatible import AiProviderError
from app.adapters.trending.base import TrendingRawItem
from app.database import get_db
from app.dependencies import get_current_worker, require_permission
from app.models import PublishWorker, User
from app.schemas import (
    ContentTemplateResponse,
    TrendingAiRecommendRequest,
    TrendingAiRecommendResponse,
    TrendingFetchResponse,
    TrendingItemResponse,
    TrendingRecommendation,
    TrendingStatusResponse,
    TrendingWorkerIngestRequest,
)
from app.services.content_template_service import ContentTemplateService
from app.services.trending_ai_recommend_service import TrendingAiRecommendService
from app.services.trending_config_service import TrendingConfigService
from app.services.trending_fetch_service import TrendingFetchService
from app.services.trending_query_service import TrendingQueryService
from app.utils.permissions import PERM_TEMPLATES_WRITE, PERM_TRENDING_READ, PERM_TRENDING_WRITE

router = APIRouter(prefix="/api/trending", tags=["trending"])


def _ensure_enabled(db: Session) -> None:
    if not TrendingConfigService(db).enabled():
        raise HTTPException(status_code=400, detail="热点灵感未启用，请在系统设置中开启")


@router.get("/status", response_model=TrendingStatusResponse)
def trending_status(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PERM_TRENDING_READ)),
):
    return TrendingQueryService(db).status()


@router.get("/items", response_model=list[TrendingItemResponse])
def list_trending_items(
    period: str = Query(default="daily"),
    platform: str | None = Query(default=None),
    category: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PERM_TRENDING_READ)),
):
    _ensure_enabled(db)
    rows = TrendingQueryService(db).list_items(
        period=period,
        platform=platform,
        category=category,
        limit=limit,
    )
    return [TrendingItemResponse(**row) for row in rows]


@router.post("/fetch", response_model=TrendingFetchResponse)
async def fetch_trending(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PERM_TRENDING_WRITE)),
):
    _ensure_enabled(db)
    service = TrendingFetchService(db)
    try:
        run = await service.fetch_all()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return TrendingFetchResponse(
        id=run.id,
        source=run.source,
        mode=run.mode,
        status=run.status,
        item_count=run.item_count,
        error_message=run.error_message,
        started_at=run.started_at,
        finished_at=run.finished_at,
    )


@router.post("/ai-recommend", response_model=TrendingAiRecommendResponse)
async def ai_recommend(
    data: TrendingAiRecommendRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PERM_TRENDING_READ)),
):
    _ensure_enabled(db)
    service = TrendingAiRecommendService(db)
    try:
        result = await service.recommend(
            period=data.period,
            platform=data.platform,
            category=data.category,
            limit=data.limit,
        )
    except AiProviderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return TrendingAiRecommendResponse(
        recommendations=[TrendingRecommendation(**row) for row in result.get("recommendations", [])],
        provider=result.get("provider"),
        message=result.get("message"),
    )


@router.post("/items/{item_id}/save-template", response_model=ContentTemplateResponse)
def save_trending_as_template(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PERM_TEMPLATES_WRITE)),
):
    _ensure_enabled(db)
    row = TrendingQueryService(db).get_item(item_id)
    if not row:
        raise HTTPException(status_code=404, detail="热点条目不存在")
    template = ContentTemplateService(db).create(
        name=f"热点-{row.title[:40]}",
        industry="热点灵感",
        topic=row.title,
        platform=row.platform,
        content_type="video",
        title_hint=row.title[:256],
        tags=row.tags or [],
    )
    return template


@router.post("/worker/ingest", response_model=TrendingFetchResponse)
async def worker_ingest_trending(
    data: TrendingWorkerIngestRequest,
    db: Session = Depends(get_db),
    worker: PublishWorker = Depends(get_current_worker),
):
    if not TrendingConfigService(db).enabled():
        raise HTTPException(status_code=400, detail="热点灵感未启用")
    raw_items = [
        TrendingRawItem(
            platform=item.platform,
            rank=item.rank,
            title=item.title,
            heat_score=item.heat_score,
            source_url=item.source_url,
            cover_url=item.cover_url,
            video_url=item.video_url,
            tags=item.tags,
        )
        for item in data.items
    ]
    run = await TrendingFetchService(db).ingest_raw_items(
        raw_items,
        source="local_worker",
        mode="local_worker",
    )
    return TrendingFetchResponse(
        id=run.id,
        source=run.source,
        mode=run.mode,
        status=run.status,
        item_count=run.item_count,
        error_message=run.error_message,
        started_at=run.started_at,
        finished_at=run.finished_at,
    )


@router.get("/worker/job")
def worker_trending_job(
    db: Session = Depends(get_db),
    worker: PublishWorker = Depends(get_current_worker),
):
    """本机 Worker 轮询：是否需要执行热点抓取（local_worker / auto 模式）。"""
    config = TrendingConfigService(db)
    if not config.enabled():
        return {"fetch": False}
    mode = config.fetch_mode()
    if mode not in {"local_worker", "auto"}:
        return {"fetch": False}
    return {
        "fetch": True,
        "platforms": ["douyin", "bilibili"],
        "dailyhot_base_url": config.dailyhot_base_url(),
    }
