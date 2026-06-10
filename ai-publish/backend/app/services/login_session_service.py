from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.adapters.base import LoginResult


@dataclass
class LoginSession:
    session_id: str
    account_id: int
    status: str = "starting"
    qrcode_data_url: str = ""
    qrcode_path: str = ""
    message: str = "正在启动浏览器..."
    success: bool = False
    login_status: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    task: asyncio.Task | None = field(default=None, repr=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "account_id": self.account_id,
            "status": self.status,
            "qrcode_data_url": self.qrcode_data_url,
            "qrcode_path": self.qrcode_path,
            "message": self.message,
            "success": self.success,
            "login_status": self.login_status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def touch(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)
        self.updated_at = datetime.now(timezone.utc).isoformat()


class LoginSessionService:
    _sessions: dict[str, LoginSession] = {}
    _lock = asyncio.Lock()

    async def create(self, account_id: int) -> LoginSession:
        session = LoginSession(session_id=uuid.uuid4().hex, account_id=account_id)
        async with self._lock:
            self._sessions[session.session_id] = session
        return session

    async def get(self, session_id: str) -> LoginSession | None:
        async with self._lock:
            return self._sessions.get(session_id)

    async def finish(self, session_id: str, result: LoginResult) -> LoginSession | None:
        async with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return None
            session.touch(
                success=result.success,
                login_status=result.status,
                message=result.message,
                status="success" if result.success else result.status or "failed",
                qrcode_data_url=result.qrcode_data_url or session.qrcode_data_url,
                qrcode_path=result.qrcode_path or session.qrcode_path,
            )
            return session

    async def cleanup(self, session_id: str) -> None:
        async with self._lock:
            self._sessions.pop(session_id, None)


login_session_service = LoginSessionService()
