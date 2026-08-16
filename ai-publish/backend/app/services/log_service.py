from datetime import datetime

from sqlalchemy.orm import Session

from app.models import AiGenerationRecord, OperationLog


class LogService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_ai_records(
        self,
        record_type: str | None = None,
        provider: str | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        limit: int = 100,
    ) -> list[AiGenerationRecord]:
        query = self.db.query(AiGenerationRecord)
        if record_type:
            query = query.filter(AiGenerationRecord.type == record_type)
        if provider:
            query = query.filter(AiGenerationRecord.provider == provider)
        if created_from:
            query = query.filter(AiGenerationRecord.created_at >= created_from)
        if created_to:
            query = query.filter(AiGenerationRecord.created_at <= created_to)
        return query.order_by(AiGenerationRecord.id.desc()).limit(limit).all()

    def list_operation_logs(
        self,
        action: str | None = None,
        target_type: str | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        limit: int = 100,
    ) -> list[OperationLog]:
        query = self.db.query(OperationLog)
        if action:
            query = query.filter(OperationLog.action == action)
        if target_type:
            query = query.filter(OperationLog.target_type == target_type)
        if created_from:
            query = query.filter(OperationLog.created_at >= created_from)
        if created_to:
            query = query.filter(OperationLog.created_at <= created_to)
        return query.order_by(OperationLog.id.desc()).limit(limit).all()

    def add_operation(
        self,
        action: str,
        user_id: int | None = None,
        target_type: str | None = None,
        target_id: int | None = None,
        ip: str | None = None,
    ) -> None:
        log = OperationLog(
            action=action,
            user_id=user_id,
            target_type=target_type,
            target_id=target_id,
            ip=ip,
        )
        self.db.add(log)
        self.db.commit()
