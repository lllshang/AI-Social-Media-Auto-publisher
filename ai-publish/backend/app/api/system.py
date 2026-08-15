from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.services.system_config_service import SystemConfigService
from app.utils.runtime_env import get_runtime_info

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/runtime")
def runtime_info(_: User = Depends(get_current_user)):
    return get_runtime_info()


@router.get("/features")
def system_features(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """登录用户可读的系统开关（用于发布向导等页面）。"""
    config = SystemConfigService(db)
    return {
        "require_content_review": config.require_content_review(),
        "scheduler_enabled": config.scheduler_enabled(),
        "trending_enabled": config.trending_enabled(),
    }
