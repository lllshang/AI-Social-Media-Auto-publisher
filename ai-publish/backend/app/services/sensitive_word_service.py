from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import PublishTask, SensitiveWord
from app.services.system_config_service import SystemConfigService


@dataclass
class SensitiveWordHit:
    field: str
    word: str


@dataclass
class SensitiveWordCheckResult:
    hits: list[SensitiveWordHit]

    @property
    def blocked(self) -> bool:
        return bool(self.hits)

    def message(self) -> str:
        if not self.hits:
            return ""
        parts = [f"{hit.field} 含「{hit.word}」" for hit in self.hits[:5]]
        suffix = f" 等 {len(self.hits)} 处" if len(self.hits) > 5 else ""
        return "敏感词检测未通过：" + "；".join(parts) + suffix


class SensitiveWordService:
    FIELD_LABELS = {
        "title": "标题",
        "content": "正文",
        "cover_text": "封面文案",
        "comment_guide": "评论引导",
        "tags": "标签",
        "topic": "主题",
    }

    def __init__(self, db: Session) -> None:
        self.db = db
        self.system_config = SystemConfigService(db)
        self._active_words: list[str] | None = None

    def enabled(self) -> bool:
        return self.system_config.sensitive_word_enabled()

    def action(self) -> str:
        return self.system_config.sensitive_word_action()

    def should_block(self) -> bool:
        return self.enabled() and self.action() == "block"

    def list_words(self, *, include_disabled: bool = False) -> list[SensitiveWord]:
        query = self.db.query(SensitiveWord)
        if not include_disabled:
            query = query.filter(SensitiveWord.enabled.is_(True))
        return query.order_by(SensitiveWord.id.desc()).all()

    def add_word(self, word: str, remark: str | None = None) -> SensitiveWord:
        normalized = word.strip()
        if not normalized:
            raise ValueError("敏感词不能为空")
        exists = (
            self.db.query(SensitiveWord)
            .filter(SensitiveWord.word == normalized)
            .first()
        )
        if exists:
            raise ValueError("敏感词已存在")
        row = SensitiveWord(word=normalized, remark=remark, enabled=True)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        self._active_words = None
        return row

    def delete_word(self, word_id: int) -> None:
        row = self.db.query(SensitiveWord).filter(SensitiveWord.id == word_id).first()
        if not row:
            raise ValueError("敏感词不存在")
        self.db.delete(row)
        self.db.commit()
        self._active_words = None

    def batch_import(self, words: list[str]) -> int:
        added = 0
        for raw in words:
            word = raw.strip()
            if not word:
                continue
            exists = (
                self.db.query(SensitiveWord)
                .filter(SensitiveWord.word == word)
                .first()
            )
            if exists:
                continue
            self.db.add(SensitiveWord(word=word, enabled=True))
            added += 1
        if added:
            self.db.commit()
            self._active_words = None
        return added

    def _active_word_list(self) -> list[str]:
        if self._active_words is None:
            rows = self.list_words(include_disabled=False)
            self._active_words = [row.word for row in rows if row.word]
        return self._active_words

    def collect_text_fields(
        self,
        *,
        title: str | None = None,
        content: str | None = None,
        cover_text: str | None = None,
        comment_guide: str | None = None,
        topic: str | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, str]:
        fields: dict[str, str] = {}
        if title:
            fields["title"] = title
        if content:
            fields["content"] = content
        if cover_text:
            fields["cover_text"] = cover_text
        if comment_guide:
            fields["comment_guide"] = comment_guide
        if topic:
            fields["topic"] = topic
        if tags:
            joined = " ".join(str(tag) for tag in tags if tag)
            if joined:
                fields["tags"] = joined
        return fields

    def scan_fields(self, fields: dict[str, str]) -> SensitiveWordCheckResult:
        if not self.enabled():
            return SensitiveWordCheckResult(hits=[])
        words = self._active_word_list()
        if not words:
            return SensitiveWordCheckResult(hits=[])
        hits: list[SensitiveWordHit] = []
        for field, text in fields.items():
            lowered = text.casefold()
            for word in words:
                if word.casefold() in lowered:
                    hits.append(SensitiveWordHit(field=self.FIELD_LABELS.get(field, field), word=word))
        return SensitiveWordCheckResult(hits=hits)

    def check_task(self, task: PublishTask) -> SensitiveWordCheckResult:
        fields = self.collect_text_fields(
            title=task.title,
            content=task.content,
            cover_text=task.cover_text,
            comment_guide=task.comment_guide,
            topic=task.topic,
            tags=task.tags,
        )
        return self.scan_fields(fields)

    def enforce_task(self, task: PublishTask, *, log_callback=None) -> SensitiveWordCheckResult:
        result = self.check_task(task)
        if not result.hits:
            return result
        if log_callback:
            log_callback(result)
        if self.should_block():
            raise ValueError(result.message())
        return result
