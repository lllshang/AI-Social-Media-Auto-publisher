from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas import LoginRequest, LoginResponse
from app.services.auth_service import authenticate_user, create_access_token
from app.services.rbac_service import RbacService
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
def me(user: User = Depends(get_current_user)):
    return {
        "username": user.username,
        "role_name": getattr(user, "role_name", "operator"),
        "permissions": getattr(user, "permissions", []),
    }
