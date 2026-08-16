from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_permission
from app.models import User
from app.schemas import SystemConfigResponse
from app.services.log_service import LogService
from app.services.system_config_service import SystemConfigService
from app.utils.permissions import PERM_SETTINGS_WRITE
from app.utils.request_ip import get_client_ip

router = APIRouter(prefix="/api/system/configs", tags=["system-configs"])


class SystemConfigUpdateRequest(BaseModel):
    config_value: str | None = None
    remark: str | None = None


@router.get("", response_model=list[SystemConfigResponse])
def list_configs(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PERM_SETTINGS_WRITE)),
):
    service = SystemConfigService(db)
    return service.list_configs()


@router.put("/{config_key}", response_model=SystemConfigResponse)
def update_config(
    config_key: str,
    data: SystemConfigUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PERM_SETTINGS_WRITE)),
):
    service = SystemConfigService(db)
    row = service.set_value(config_key, data.config_value, data.remark)
    LogService(db).add_operation(
        "system_config.update",
        current_user.id,
        "system_config",
        row.id,
        ip=get_client_ip(request),
    )
    return row
