from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import ContentTemplate


class ContentTemplateService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, template_id: int) -> ContentTemplate | None:
        return self.db.query(ContentTemplate).filter(ContentTemplate.id == template_id).first()

    def list_templates(
        self,
        *,
        industry: str | None = None,
        platform: str | None = None,
        status: str | None = "active",
        include_disabled: bool = False,
    ) -> list[ContentTemplate]:
        query = self.db.query(ContentTemplate)
        if not include_disabled:
            query = query.filter(ContentTemplate.status == (status or "active"))
        elif status:
            query = query.filter(ContentTemplate.status == status)
        if industry:
            query = query.filter(ContentTemplate.industry == industry)
        if platform:
            query = query.filter(
                (ContentTemplate.platform == platform) | (ContentTemplate.platform.is_(None))
            )
        return query.order_by(ContentTemplate.id.desc()).all()

    def list_industries(self) -> list[str]:
        rows = (
            self.db.query(ContentTemplate.industry)
            .filter(ContentTemplate.status == "active")
            .distinct()
            .all()
        )
        return sorted({row[0] for row in rows if row[0]})

    def create(
        self,
        *,
        name: str,
        industry: str,
        topic: str,
        platform: str | None = None,
        content_type: str = "note",
        template_kind: str = "text",
        title_hint: str | None = None,
        content_body: str | None = None,
        tags: list[str] | None = None,
        image_style: str | None = None,
        image_ratio: str | None = None,
        brand_color: str | None = None,
        brand_hint: str | None = None,
        status: str = "active",
    ) -> ContentTemplate:
        row = ContentTemplate(
            name=name,
            industry=industry,
            platform=platform,
            content_type=content_type,
            template_kind=template_kind,
            topic=topic,
            title_hint=title_hint,
            content_body=content_body,
            tags=tags or [],
            image_style=image_style,
            image_ratio=image_ratio,
            brand_color=brand_color,
            brand_hint=brand_hint,
            status=status,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def update(
        self,
        template_id: int,
        *,
        name: str | None = None,
        industry: str | None = None,
        platform: str | None = None,
        content_type: str | None = None,
        template_kind: str | None = None,
        topic: str | None = None,
        title_hint: str | None = None,
        content_body: str | None = None,
        tags: list[str] | None = None,
        image_style: str | None = None,
        image_ratio: str | None = None,
        brand_color: str | None = None,
        brand_hint: str | None = None,
        status: str | None = None,
    ) -> ContentTemplate:
        row = self.get(template_id)
        if not row:
            raise ValueError("模板不存在")
        if name is not None:
            row.name = name
        if industry is not None:
            row.industry = industry
        if platform is not None:
            row.platform = platform or None
        if content_type is not None:
            row.content_type = content_type
        if template_kind is not None:
            row.template_kind = template_kind
        if topic is not None:
            row.topic = topic
        if title_hint is not None:
            row.title_hint = title_hint
        if content_body is not None:
            row.content_body = content_body
        if tags is not None:
            row.tags = tags
        if image_style is not None:
            row.image_style = image_style
        if image_ratio is not None:
            row.image_ratio = image_ratio
        if brand_color is not None:
            row.brand_color = brand_color
        if brand_hint is not None:
            row.brand_hint = brand_hint
        if status is not None:
            row.status = status
        self.db.commit()
        self.db.refresh(row)
        return row


def ensure_default_content_templates(db: Session) -> None:
    service = ContentTemplateService(db)
    if service.list_templates(include_disabled=True):
        return
    service.create(
        name="春茶上新图文",
        industry="茶叶",
        platform="xhs",
        content_type="note",
        template_kind="bundle",
        topic="高山有机春茶上新",
        title_hint="一口喝到春天的鲜爽",
        content_body="围绕春茶采摘、工艺与口感撰写种草笔记，突出产地与有机认证，结尾引导评论互动。",
        tags=["春茶", "有机茶", "喝茶日常"],
        image_style="default",
        image_ratio="3:4",
        brand_color="#2E8B57",
        brand_hint="高山有机春茶，鲜爽回甘",
    )
    service.create(
        name="电商大促短视频",
        industry="电商",
        platform="douyin",
        content_type="video",
        template_kind="bundle",
        topic="618限时福利开箱",
        title_hint="这次福利真的划算",
        content_body="短视频脚本：开场钩子→产品亮点3条→限时优惠→评论区领券引导。",
        tags=["618", "好物推荐", "限时优惠"],
        image_style="vivid",
        image_ratio="9:16",
        brand_color="#FF4500",
        brand_hint="品牌官方直营，限时直降",
    )
