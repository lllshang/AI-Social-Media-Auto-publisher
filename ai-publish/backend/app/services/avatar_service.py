"""数字人 / 仿真人 Avatar 服务。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.adapters.factory import get_adapter_factory
from app.models import Avatar
from app.schemas import AvatarCreate, AvatarResponse, AvatarUpdate


class AvatarService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.factory = get_adapter_factory()

    def to_response(self, avatar: Avatar) -> AvatarResponse:
        storage = self.factory.get_storage_adapter()
        thumbnail_url = storage.get_url(avatar.thumbnail) if avatar.thumbnail else None
        # 带背景参考图同样走 storage 转换为可访问的 URL(此前直接透传相对路径导致前端加载失败)
        background_image_url = (
            storage.get_url(avatar.background_image_url)
            if avatar.background_image_url
            else None
        )
        return AvatarResponse(
            id=avatar.id,
            name=avatar.name,
            type=avatar.type,
            gender=avatar.gender,
            config=avatar.config,
            reference_images=avatar.reference_images,
            reference_image_url=avatar.reference_image_url,
            reference_video_url=avatar.reference_video_url,
            thumbnail_url=thumbnail_url,
            background_prompt=avatar.background_prompt,
            background_image_url=background_image_url,
            status=avatar.status,
            created_at=avatar.created_at,
            updated_at=avatar.updated_at,
        )

    def list_avatars(self, type: str | None = None) -> list[Avatar]:
        query = self.db.query(Avatar).filter(Avatar.status == "active")
        if type and type != "all":
            query = query.filter(Avatar.type == type)
        return query.order_by(Avatar.id.desc()).all()

    def get(self, avatar_id: int) -> Avatar | None:
        return self.db.query(Avatar).filter(Avatar.id == avatar_id, Avatar.status == "active").first()

    def create(self, data: AvatarCreate, user_id: int | None = None) -> Avatar:
        avatar = Avatar(
            name=data.name,
            type=data.type,
            gender=data.gender,
            config=data.config,
            reference_images=data.reference_images,
            reference_image_url=data.reference_image_url,
            reference_video_url=data.reference_video_url,
            background_prompt=data.background_prompt,
            background_image_url=data.background_image_url,
            created_by=user_id,
        )
        self.db.add(avatar)
        self.db.commit()
        self.db.refresh(avatar)
        return avatar

    def update(self, avatar_id: int, data: AvatarUpdate) -> Avatar:
        avatar = self.get(avatar_id)
        if not avatar:
            raise ValueError("Avatar 不存在")
        for field, value in data.model_dump(exclude_unset=True).items():
            if value is not None:
                setattr(avatar, field, value)
        self.db.commit()
        self.db.refresh(avatar)
        return avatar

    def delete(self, avatar_id: int) -> None:
        avatar = self.get(avatar_id)
        if not avatar:
            raise ValueError("Avatar 不存在")
        avatar.status = "deleted"
        self.db.commit()
