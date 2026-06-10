from sqlalchemy.orm import Session

from app.adapters.base import PublishContext
from app.adapters.factory import get_adapter_factory
from app.models import PublishTask
from app.services.material_service import MaterialService
from app.services.platform_account_service import PlatformAccountService


class UploadWorker:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.factory = get_adapter_factory()
        self.account_service = PlatformAccountService(db)
        self.material_service = MaterialService(db)

    async def run(self, task: PublishTask):
        account = self.account_service.get_account(task.account_id)
        if not account:
            raise ValueError("账号不存在")
        cookie_file = self.account_service.sync_cookie_file(account)
        material_paths: list[str] = []
        for material_id in task.material_ids or []:
            material = self.material_service.get(material_id)
            if material:
                material_paths.append(material.file_path)

        async def log_callback(step: str, status: str, message: str) -> None:
            from app.models import PublishTaskLog

            log = PublishTaskLog(task_id=task.id, step=step, status=status, message=message)
            self.db.add(log)
            self.db.commit()

        context = PublishContext(
            task_id=task.id,
            platform=task.platform,
            account_id=task.account_id,
            account_name=account.account_name,
            cookie_file=cookie_file,
            title=task.title,
            content=task.content or "",
            tags=task.tags or [],
            content_type=task.content_type,
            material_paths=material_paths,
            publish_time=task.publish_time,
            log_callback=log_callback,
        )
        adapter = self.factory.get_platform_adapter(task.platform)
        return await adapter.publish(context)
