from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas import ChangePasswordRequest, LoginRequest, LoginResponse
from app.services.auth_service import authenticate_user, create_access_token
from app.services.log_service import LogService
from app.services.rbac_service import RbacService
from app.services.user_service import UserService
from app.utils.request_ip import get_client_ip
from app.utils.permissions import get_user_permissions

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, data.username, data.password)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    rbac = RbacService(db)
    role = rbac.get_role(user.role_id)
    permissions = get_user_permissions(user, rbac.get_role_permissions(user))
    token = create_access_token({"sub": user.id, "username": user.username})
    return LoginResponse(
        access_token=token,
        username=user.username,
        role_name=role.role_name if role else "operator",
        permissions=permissions,
    )


@router.get("/me")
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # 注意：必须和 /login 一样按「角色」计算权限，不能返回 user.permissions
    # （那是用户自定义权限字段，大部分用户为空数组）。
    # 否则前端 refreshSession() 会把本地正确的权限覆盖成空数组，
    # 触发 dashboard 路由守卫权限不足 → 重定向回 dashboard 的死循环 → 白屏。
    rbac = RbacService(db)
    role = rbac.get_role(user.role_id)
    permissions = get_user_permissions(user, rbac.get_role_permissions(user))
    return {
        "username": user.username,
        "role_name": role.role_name if role else "operator",
        "permissions": permissions,
    }


@router.post("/change-password")
def change_password(
    data: ChangePasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    service = UserService(db)
    try:
        service.change_password(user, data.old_password, data.new_password)
        LogService(db).add_operation(
            "user.change_password",
            user.id,
            "user",
            user.id,
            ip=get_client_ip(request),
        )
        return {"ok": True}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
