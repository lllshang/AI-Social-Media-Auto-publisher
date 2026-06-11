from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import PublishWorker, User
from app.services.publish_worker_service import PublishWorkerService
from app.services.auth_service import decode_access_token
from app.services.rbac_service import RbacService
from app.utils.permissions import get_user_permissions, has_permission

security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录")
    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token 无效")
    user = db.query(User).filter(User.id == int(payload.get("sub")), User.status == "active").first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")
    role_permissions = RbacService(db).get_role_permissions(user)
    user.permissions = get_user_permissions(user, role_permissions)  # type: ignore[attr-defined]
    role = RbacService(db).get_role(user.role_id)
    user.role_name = role.role_name if role else "operator"  # type: ignore[attr-defined]
    return user


def require_permission(permission: str) -> Callable:
    def _checker(user: User = Depends(get_current_user)) -> User:
        perms = getattr(user, "permissions", [])
        if not has_permission(perms, permission):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限执行此操作")
        return user

    return _checker


def require_any_permission(*permissions: str) -> Callable:
    def _checker(user: User = Depends(get_current_user)) -> User:
        perms = getattr(user, "permissions", [])
        if not any(has_permission(perms, item) for item in permissions):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限执行此操作")
        return user

    return _checker


def get_current_worker(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> PublishWorker:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少 Worker Token")
    worker = PublishWorkerService(db).get_worker_by_token(credentials.credentials)
    if not worker:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Worker Token 无效")
    return worker
