from datetime import datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGORITHM = "HS256"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict[str, Any]) -> str:
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({"exp": expire})
    to_encode["sub"] = str(to_encode["sub"])
    return jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any] | None:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except JWTError:
        return None


def authenticate_user(db: Session, username: str, password: str) -> User | None:
    user = db.query(User).filter(User.username == username, User.status == "active").first()
    if not user or not verify_password(password, user.password_hash):
        return None
    return user


def ensure_admin_user(db: Session) -> None:
    from app.services.rbac_service import assign_admin_role, ensure_default_roles

    settings = get_settings()
    ensure_default_roles(db)
    exists = db.query(User).filter(User.username == settings.admin_username).first()
    if exists:
        assign_admin_role(db, settings.admin_username)
        return
    user = User(
        username=settings.admin_username,
        password_hash=hash_password(settings.admin_password),
        status="active",
    )
    db.add(user)
    db.commit()
    assign_admin_role(db, settings.admin_username)
