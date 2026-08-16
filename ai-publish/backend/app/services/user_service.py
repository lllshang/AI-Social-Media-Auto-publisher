from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Role, User
from app.services.auth_service import hash_password, verify_password


class UserService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_users(self) -> list[User]:
        return self.db.query(User).order_by(User.id.asc()).all()

    def get_user(self, user_id: int) -> User | None:
        return self.db.query(User).filter(User.id == user_id).first()

    def create_user(self, username: str, password: str, role_id: int | None = None) -> User:
        username = username.strip()
        if not username:
            raise ValueError("用户名不能为空")
        if len(password) < 6:
            raise ValueError("密码至少 6 位")
        exists = self.db.query(User).filter(User.username == username).first()
        if exists:
            raise ValueError("用户名已存在")
        if role_id:
            role = self.db.query(Role).filter(Role.id == role_id).first()
            if not role:
                raise ValueError("角色不存在")
        user = User(
            username=username,
            password_hash=hash_password(password),
            role_id=role_id,
            status="active",
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update_user(
        self,
        user_id: int,
        *,
        role_id: int | None = None,
        status: str | None = None,
        actor_id: int | None = None,
    ) -> User:
        user = self.get_user(user_id)
        if not user:
            raise ValueError("用户不存在")
        if actor_id and user_id == actor_id and status == "disabled":
            raise ValueError("不能禁用当前登录账号")
        if role_id is not None:
            role = self.db.query(Role).filter(Role.id == role_id).first()
            if not role:
                raise ValueError("角色不存在")
            user.role_id = role_id
        if status is not None:
            if status not in {"active", "disabled"}:
                raise ValueError("状态仅支持 active 或 disabled")
            user.status = status
        self.db.commit()
        self.db.refresh(user)
        return user

    def reset_password(self, user_id: int, new_password: str) -> None:
        if len(new_password) < 6:
            raise ValueError("密码至少 6 位")
        user = self.get_user(user_id)
        if not user:
            raise ValueError("用户不存在")
        user.password_hash = hash_password(new_password)
        self.db.commit()

    def change_password(self, user: User, old_password: str, new_password: str) -> None:
        if not verify_password(old_password, user.password_hash):
            raise ValueError("原密码不正确")
        if len(new_password) < 6:
            raise ValueError("新密码至少 6 位")
        user.password_hash = hash_password(new_password)
        self.db.commit()
