from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_permission
from app.models import Role, User
from app.schemas import UserCreateRequest, UserResetPasswordRequest, UserResponse, UserUpdateRequest
from app.services.log_service import LogService
from app.services.user_service import UserService
from app.utils.permissions import PERM_USERS_WRITE
from app.utils.request_ip import get_client_ip

router = APIRouter(prefix="/api/users", tags=["users"])


def _role_map(db: Session) -> dict[int, str]:
    return {role.id: role.role_name for role in db.query(Role).all()}


def _user_response(user: User, roles: dict[int, str]) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        role_id=user.role_id,
        role_name=roles.get(user.role_id, ""),
        status=user.status,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.get("", response_model=list[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PERM_USERS_WRITE)),
):
    service = UserService(db)
    roles = _role_map(db)
    return [_user_response(user, roles) for user in service.list_users()]


@router.post("", response_model=UserResponse)
def create_user(
    data: UserCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PERM_USERS_WRITE)),
):
    service = UserService(db)
    try:
        user = service.create_user(data.username, data.password, data.role_id)
        LogService(db).add_operation(
            "user.create",
            current_user.id,
            "user",
            user.id,
            ip=get_client_ip(request),
        )
        return _user_response(user, _role_map(db))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    data: UserUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PERM_USERS_WRITE)),
):
    service = UserService(db)
    try:
        user = service.update_user(
            user_id,
            role_id=data.role_id,
            status=data.status,
            actor_id=current_user.id,
        )
        LogService(db).add_operation(
            "user.update",
            current_user.id,
            "user",
            user.id,
            ip=get_client_ip(request),
        )
        return _user_response(user, _role_map(db))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{user_id}/reset-password")
def reset_user_password(
    user_id: int,
    data: UserResetPasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PERM_USERS_WRITE)),
):
    service = UserService(db)
    try:
        service.reset_password(user_id, data.new_password)
        LogService(db).add_operation(
            "user.reset_password",
            current_user.id,
            "user",
            user_id,
            ip=get_client_ip(request),
        )
        return {"ok": True}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
