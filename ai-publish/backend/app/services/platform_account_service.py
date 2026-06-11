from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.adapters.base import LoginResult
from app.adapters.factory import get_adapter_factory
from app.config import get_settings
from app.models import AccountCookie, PlatformAccount
from app.services.log_service import LogService
from app.utils.crypto import decrypt_text, encrypt_text


class PlatformAccountService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.factory = get_adapter_factory()

    def list_accounts(
        self,
        platform: str | None = None,
        group_id: int | None = None,
    ) -> list[PlatformAccount]:
        query = self.db.query(PlatformAccount)
        if platform:
            query = query.filter(PlatformAccount.platform == platform)
        if group_id is not None:
            query = query.filter(PlatformAccount.group_id == group_id)
        return query.order_by(PlatformAccount.id.desc()).all()

    def create_account(self, platform: str, account_name: str, user_id: int | None = None) -> PlatformAccount:
        exists = (
            self.db.query(PlatformAccount)
            .filter(PlatformAccount.platform == platform, PlatformAccount.account_name == account_name)
            .first()
        )
        if exists:
            raise ValueError("账号已存在")
        account = PlatformAccount(
            platform=platform,
            account_name=account_name,
            status="inactive",
            created_by=user_id,
        )
        self.db.add(account)
        self.db.commit()
        self.db.refresh(account)
        return account

    def update_account(
        self,
        account_id: int,
        *,
        account_name: str | None = None,
        remark: str | None = None,
    ) -> PlatformAccount:
        account = self.get_account(account_id)
        if not account:
            raise ValueError("账号不存在")
        if account_name is not None:
            name = account_name.strip()
            if not name:
                raise ValueError("账号名不能为空")
            exists = (
                self.db.query(PlatformAccount)
                .filter(
                    PlatformAccount.platform == account.platform,
                    PlatformAccount.account_name == name,
                    PlatformAccount.id != account_id,
                )
                .first()
            )
            if exists:
                raise ValueError("同平台下账号名已存在")
            account.account_name = name
        if remark is not None:
            account.remark = remark.strip() or None
        self.db.commit()
        self.db.refresh(account)
        return account

    def get_account(self, account_id: int) -> PlatformAccount | None:
        return self.db.query(PlatformAccount).filter(PlatformAccount.id == account_id).first()

    def cookie_file_path(self, account: PlatformAccount) -> str:
        path = self.settings.cookie_path / account.platform / f"{account.id}_{account.account_name}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        return str(path)

    def save_cookie(self, account: PlatformAccount, cookie_plain: str) -> None:
        encrypted = encrypt_text(cookie_plain, self.settings.cookie_encryption_key)
        record = self.db.query(AccountCookie).filter(AccountCookie.account_id == account.id).first()
        if record:
            record.cookie_data = encrypted
            record.updated_at = datetime.utcnow()
        else:
            record = AccountCookie(account_id=account.id, cookie_data=encrypted)
            self.db.add(record)
        account.status = "active"
        self.db.commit()

    def load_cookie_plain(self, account: PlatformAccount) -> str | None:
        record = self.db.query(AccountCookie).filter(AccountCookie.account_id == account.id).first()
        if not record:
            return None
        return decrypt_text(record.cookie_data, self.settings.cookie_encryption_key)

    def sync_cookie_file(self, account: PlatformAccount) -> str:
        cookie_plain = self.load_cookie_plain(account)
        cookie_file = self.cookie_file_path(account)
        if cookie_plain:
            Path(cookie_file).write_text(cookie_plain, encoding="utf-8")
        return cookie_file

    async def login(self, account_id: int, qrcode_callback=None) -> LoginResult:
        account = self.get_account(account_id)
        if not account:
            raise ValueError("账号不存在")
        adapter = self.factory.get_platform_adapter(account.platform)
        cookie_file = self.cookie_file_path(account)
        result = await adapter.login(account.id, account.account_name, cookie_file, qrcode_callback=qrcode_callback)
        if result.success and Path(cookie_file).exists():
            cookie_plain = Path(cookie_file).read_text(encoding="utf-8")
            self.save_cookie(account, cookie_plain)
        return result

    async def check_cookie(
        self,
        account_id: int,
        *,
        user_id: int | None = None,
        ip: str | None = None,
    ) -> dict:
        account = self.get_account(account_id)
        if not account:
            raise ValueError("账号不存在")
        prev_status = account.status
        cookie_file = self.sync_cookie_file(account)
        if not Path(cookie_file).exists():
            account.status = "expired"
            self._log_account_expired(account, prev_status, user_id, ip)
            self.db.commit()
            return {"valid": False, "status": account.status}
        adapter = self.factory.get_platform_adapter(account.platform)
        valid = await adapter.check_cookie_valid(cookie_file)
        account.status = "active" if valid else "expired"
        if not valid:
            self._log_account_expired(account, prev_status, user_id, ip)
        if valid:
            cookie_plain = Path(cookie_file).read_text(encoding="utf-8")
            self.save_cookie(account, cookie_plain)
        self.db.commit()
        return {"valid": valid, "status": account.status}

    def _log_account_expired(
        self,
        account: PlatformAccount,
        prev_status: str,
        user_id: int | None,
        ip: str | None,
    ) -> None:
        if prev_status != "expired":
            LogService(self.db).add_operation(
                "platform_account.expired",
                user_id,
                "platform_account",
                account.id,
                ip=ip,
            )

    def delete_account(self, account_id: int) -> None:
        from app.models import PublishTask

        account = self.get_account(account_id)
        if not account:
            raise ValueError("账号不存在")
        task_count = self.db.query(PublishTask).filter(PublishTask.account_id == account_id).count()
        if task_count:
            raise ValueError(f"该账号关联 {task_count} 条发布任务，请先处理任务后再删除")
        cookie_file = Path(self.cookie_file_path(account))
        if cookie_file.exists():
            cookie_file.unlink()
        self.db.query(AccountCookie).filter(AccountCookie.account_id == account_id).delete()
        self.db.delete(account)
        self.db.commit()
