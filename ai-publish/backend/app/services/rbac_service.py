from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Role, User
from app.utils.permissions import ADMIN_PERMISSIONS, OPERATOR_PERMISSIONS, VIEWER_PERMISSIONS


class RbacService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_role(self, role_id: int | None) -> Role | None:
        if not role_id:
            return None
        return self.db.query(Role).filter(Role.id == role_id).first()

    def get_role_permissions(self, user: User) -> list[str] | None:
        role = self.get_role(user.role_id)
        if not role:
            return None
        return role.permissions or []

    def list_roles(self) -> list[Role]:
        return self.db.query(Role).order_by(Role.id.asc()).all()


def ensure_default_roles(db: Session) -> None:
    seeds = [
        ("admin", ADMIN_PERMISSIONS),
        ("operator", OPERATOR_PERMISSIONS),
        ("viewer", VIEWER_PERMISSIONS),
    ]
    for role_name, permissions in seeds:
        exists = db.query(Role).filter(Role.role_name == role_name).first()
        if exists:
            exists.permissions = permissions
        else:
            db.add(Role(role_name=role_name, permissions=permissions))
    db.commit()


def assign_admin_role(db: Session, username: str) -> None:
    admin_role = db.query(Role).filter(Role.role_name == "admin").first()
    if not admin_role:
        return
    user = db.query(User).filter(User.username == username).first()
    if user and not user.role_id:
        user.role_id = admin_role.id
        db.commit()
