from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_permission
from app.models import User
from app.schemas import RoleResponse
from app.services.rbac_service import RbacService
from app.utils.permissions import PERM_SETTINGS_WRITE

router = APIRouter(prefix="/api/roles", tags=["roles"])


@router.get("", response_model=list[RoleResponse])
def list_roles(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PERM_SETTINGS_WRITE)),
):
    service = RbacService(db)
    return service.list_roles()
