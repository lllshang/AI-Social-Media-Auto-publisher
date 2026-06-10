from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_permission
from app.models import PlatformAccount, User
from app.utils.permissions import PERM_ACCOUNTS_READ, PERM_ACCOUNTS_WRITE
from app.schemas import AccountGroupCreate, AccountGroupResponse, AccountGroupUpdate
from app.services.account_group_service import AccountGroupService
from app.services.log_service import LogService

router = APIRouter(prefix="/api/account-groups", tags=["account-groups"])


def _group_response(service: AccountGroupService, group) -> AccountGroupResponse:
    count = (
        service.db.query(func.count(PlatformAccount.id))
        .filter(PlatformAccount.group_id == group.id)
        .scalar()
        or 0
    )
    return AccountGroupResponse(
        id=group.id,
        name=group.name,
        remark=group.remark,
        account_count=int(count),
        created_at=group.created_at,
    )


@router.get("", response_model=list[AccountGroupResponse])
def list_groups(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PERM_ACCOUNTS_READ)),
):
    service = AccountGroupService(db)
    return [AccountGroupResponse(**item) for item in service.list_groups()]


@router.post("", response_model=AccountGroupResponse)
def create_group(
    data: AccountGroupCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PERM_ACCOUNTS_WRITE)),
):
    service = AccountGroupService(db)
    try:
        group = service.create_group(data.name, data.remark)
        LogService(db).add_operation("account_group.create", current_user.id, "account_group", group.id)
        return _group_response(service, group)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/{group_id}", response_model=AccountGroupResponse)
def update_group(
    group_id: int,
    data: AccountGroupUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PERM_ACCOUNTS_WRITE)),
):
    service = AccountGroupService(db)
    try:
        group = service.update_group(group_id, data.name, data.remark)
        LogService(db).add_operation("account_group.update", current_user.id, "account_group", group.id)
        return _group_response(service, group)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{group_id}")
def delete_group(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PERM_ACCOUNTS_WRITE)),
):
    service = AccountGroupService(db)
    try:
        service.delete_group(group_id)
        LogService(db).add_operation("account_group.delete", current_user.id, "account_group", group_id)
        return {"ok": True}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
