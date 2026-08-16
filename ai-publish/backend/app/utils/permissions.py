"""RBAC 权限定义与校验。"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models import User

PERM_DASHBOARD_READ = "dashboard:read"
PERM_ACCOUNTS_READ = "accounts:read"
PERM_ACCOUNTS_WRITE = "accounts:write"
PERM_MATERIALS_READ = "materials:read"
PERM_MATERIALS_WRITE = "materials:write"
PERM_TASKS_READ = "tasks:read"
PERM_TASKS_WRITE = "tasks:write"
PERM_TASKS_EXECUTE = "tasks:execute"
PERM_REVIEW_WRITE = "review:write"
PERM_PUBLISH_WRITE = "publish:write"
PERM_MODELS_READ = "models:read"
PERM_MODELS_WRITE = "models:write"
PERM_LOGS_READ = "logs:read"
PERM_SETTINGS_WRITE = "settings:write"
PERM_USERS_WRITE = "users:write"
PERM_TEMPLATES_READ = "templates:read"
PERM_TEMPLATES_WRITE = "templates:write"
PERM_TRENDING_READ = "trending:read"
PERM_TRENDING_WRITE = "trending:write"
PERM_AVATARS_READ = "avatars:read"
PERM_AVATARS_WRITE = "avatars:write"

ADMIN_PERMISSIONS = ["*"]

OPERATOR_PERMISSIONS = [
    PERM_DASHBOARD_READ,
    PERM_ACCOUNTS_READ,
    PERM_ACCOUNTS_WRITE,
    PERM_MATERIALS_READ,
    PERM_MATERIALS_WRITE,
    PERM_TASKS_READ,
    PERM_TASKS_WRITE,
    PERM_TASKS_EXECUTE,
    PERM_REVIEW_WRITE,
    PERM_PUBLISH_WRITE,
    PERM_MODELS_READ,
    PERM_MODELS_WRITE,
    PERM_LOGS_READ,
    PERM_TEMPLATES_READ,
    PERM_TEMPLATES_WRITE,
    PERM_TRENDING_READ,
    PERM_TRENDING_WRITE,
    PERM_AVATARS_READ,
    PERM_AVATARS_WRITE,
]

VIEWER_PERMISSIONS = [
    PERM_DASHBOARD_READ,
    PERM_ACCOUNTS_READ,
    PERM_MATERIALS_READ,
    PERM_TASKS_READ,
    PERM_MODELS_READ,
    PERM_LOGS_READ,
    PERM_TEMPLATES_READ,
    PERM_AVATARS_READ,
]

REVIEWER_PERMISSIONS = [
    PERM_DASHBOARD_READ,
    PERM_ACCOUNTS_READ,
    PERM_MATERIALS_READ,
    PERM_TASKS_READ,
    PERM_REVIEW_WRITE,
    PERM_TEMPLATES_READ,
]


def normalize_permissions(raw: list[str] | None) -> list[str]:
    if not raw:
        return []
    return [str(item) for item in raw]


def has_permission(permissions: list[str], required: str) -> bool:
    if "*" in permissions:
        return True
    return required in permissions


def get_user_permissions(user: User, role_permissions: list[str] | None) -> list[str]:
    if role_permissions is not None:
        return normalize_permissions(role_permissions)
    # 兼容历史用户未分配角色：默认运营权限
    return OPERATOR_PERMISSIONS.copy()


def user_has_permission(user: User, role_permissions: list[str] | None, required: str) -> bool:
    return has_permission(get_user_permissions(user, role_permissions), required)
