from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import AccountGroup, PlatformAccount


class AccountGroupService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_groups(self) -> list[dict]:
        rows = (
            self.db.query(
                AccountGroup,
                func.count(PlatformAccount.id).label("account_count"),
            )
            .outerjoin(PlatformAccount, PlatformAccount.group_id == AccountGroup.id)
            .group_by(AccountGroup.id)
            .order_by(AccountGroup.id.asc())
            .all()
        )
        return [
            {
                "id": group.id,
                "name": group.name,
                "remark": group.remark,
                "account_count": int(count),
                "created_at": group.created_at,
            }
            for group, count in rows
        ]

    def create_group(self, name: str, remark: str | None = None) -> AccountGroup:
        exists = self.db.query(AccountGroup).filter(AccountGroup.name == name).first()
        if exists:
            raise ValueError("分组名称已存在")
        group = AccountGroup(name=name, remark=remark)
        self.db.add(group)
        self.db.commit()
        self.db.refresh(group)
        return group

    def update_group(self, group_id: int, name: str | None = None, remark: str | None = None) -> AccountGroup:
        group = self.db.query(AccountGroup).filter(AccountGroup.id == group_id).first()
        if not group:
            raise ValueError("分组不存在")
        if name and name != group.name:
            exists = self.db.query(AccountGroup).filter(AccountGroup.name == name).first()
            if exists:
                raise ValueError("分组名称已存在")
            group.name = name
        if remark is not None:
            group.remark = remark
        self.db.commit()
        self.db.refresh(group)
        return group

    def delete_group(self, group_id: int) -> None:
        group = self.db.query(AccountGroup).filter(AccountGroup.id == group_id).first()
        if not group:
            raise ValueError("分组不存在")
        self.db.query(PlatformAccount).filter(PlatformAccount.group_id == group_id).update(
            {PlatformAccount.group_id: None}
        )
        self.db.delete(group)
        self.db.commit()

    def assign_account(self, account_id: int, group_id: int | None) -> PlatformAccount:
        account = self.db.query(PlatformAccount).filter(PlatformAccount.id == account_id).first()
        if not account:
            raise ValueError("账号不存在")
        if group_id is not None:
            group = self.db.query(AccountGroup).filter(AccountGroup.id == group_id).first()
            if not group:
                raise ValueError("分组不存在")
        account.group_id = group_id
        self.db.commit()
        self.db.refresh(account)
        return account

    def get_group_name(self, group_id: int | None) -> str | None:
        if not group_id:
            return None
        group = self.db.query(AccountGroup).filter(AccountGroup.id == group_id).first()
        return group.name if group else None
