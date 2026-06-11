import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Response
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger

from app.api.account_groups import router as account_groups_router
from app.api.ai_models import router as ai_models_router
from app.api.auth import router as auth_router
from app.api.dashboard import router as dashboard_router
from app.api.logs import router as logs_router
from app.api.materials import router as materials_router
from app.api.platform_accounts import router as platform_accounts_router
from app.api.publish_tasks import router as publish_tasks_router
from app.api.reviews import router as reviews_router
from app.api.roles import router as roles_router
from app.api.system import router as system_router
from app.api.system_configs import router as system_configs_router
from app.api.users import router as users_router
from app.config import BACKEND_DIR, get_settings
from app.database import SessionLocal, engine, get_db
from app.models import Base
from app.services.auth_service import ensure_admin_user
from app.services.system_config_service import ensure_default_system_configs
from app.utils.web_admin import mount_web_admin
from app.workers.redis_queue import task_queue
from app.workers.schedule_worker import schedule_worker


def setup_logging() -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
        level="DEBUG" if get_settings().debug else "INFO",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    settings = get_settings()
    settings.storage_path.mkdir(parents=True, exist_ok=True)
    settings.cookie_path.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    from app.utils.migrations import run_sqlite_migrations

    run_sqlite_migrations()
    db = SessionLocal()
    try:
        ensure_admin_user(db)
        ensure_default_system_configs(db)
    finally:
        db.close()
    logger.info("AI Publish API started")
    try:
        from app.services.ai_model_service import AiModelService

        detection = await AiModelService().detect_all()
        text = detection.text["current"]
        image = detection.image["current"]
        logger.info(
            "AI models: text={}/{} image={}/{}",
            text["provider"],
            text["model"],
            image["provider"],
            image["model"],
        )
    except Exception as exc:
        logger.warning("AI model auto-detect skipped: {}", exc)
    schedule_worker.start()
    task_queue.start_embedded_consumer()
    try:
        yield
    finally:
        task_queue.stop_embedded_consumer()
        schedule_worker.shutdown()


app = FastAPI(title=get_settings().app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:8765",
        "http://localhost:8765",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(account_groups_router)
app.include_router(ai_models_router)
app.include_router(platform_accounts_router)
app.include_router(materials_router)
app.include_router(publish_tasks_router)
app.include_router(reviews_router)
app.include_router(logs_router)
app.include_router(system_router)
app.include_router(system_configs_router)
app.include_router(roles_router)
app.include_router(users_router)

settings = get_settings()
static_dir = settings.storage_path
app.mount("/static/materials", StaticFiles(directory=str(static_dir)), name="materials")

admin_dir = BACKEND_DIR.parent / "admin"
web_dist = settings.web_dist_abs_path
if web_dist:
    mount_web_admin(app, web_dist)
elif admin_dir.exists():
    app.mount("/admin", StaticFiles(directory=str(admin_dir), html=True), name="admin")


@app.get("/health")
def health(db: Session = Depends(get_db)):
    from app.services.health_service import HealthService

    return HealthService().check(db)


@app.get("/metrics")
def metrics(db: Session = Depends(get_db)):
    from app.services.metrics_service import MetricsService

    if not settings.metrics_enabled:
        return Response(status_code=404)
    body = MetricsService(db).prometheus_text()
    return PlainTextResponse(body, media_type="text/plain; version=0.0.4; charset=utf-8")
