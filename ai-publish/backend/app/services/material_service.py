import json
import os
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.adapters.base import ImageGenerateInput, TextGenerateInput, VideoGenerateInput
from app.adapters.factory import get_adapter_factory
from app.models import AiGenerationRecord, Avatar, Material
from app.schemas import MaterialResponse
from app.services.image_moderation_service import ImageModerationService
import logging

from app.utils.thumbnail import generate_image_thumbnail

logger = logging.getLogger(__name__)


def _safe_material_name(name: str | None, limit: int = 200) -> str | None:
    """素材 name 截断保护。

    数据库 materials.name 字段早期为 VARCHAR(128)，长口播文案会触发
    DataError(1406) 导致生成任务卡死。统一在此截断，避免任意来源
    （视频 topic、图片文案、草稿标题）写入超长内容。
    """
    if not name:
        return name
    name = str(name).strip()
    if len(name) > limit:
        return name[: limit - 1].rstrip() + "…"
    return name


class MaterialService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.factory = get_adapter_factory()

    def to_response(self, material: Material, *, include_text_body: bool = False) -> MaterialResponse:
        storage = self.factory.get_storage_adapter()
        thumbnail_url = storage.get_url(material.thumbnail) if material.thumbnail else None
        text_preview = None
        text_content = None
        if material.type == "text":
            body = self._read_text_body(material.file_path)
            if body:
                text_preview = body[:200]
                if include_text_body:
                    text_content = body
        return MaterialResponse(
            id=material.id,
            type=material.type,
            source=material.source,
            name=material.name,
            category=material.category,
            file_path=material.file_path,
            url=material.url,
            thumbnail_url=thumbnail_url,
            text_preview=text_preview,
            text_content=text_content,
            moderation_status=material.moderation_status,
            moderation_detail=material.moderation_detail,
            created_at=material.created_at,
        )

    @staticmethod
    def _read_text_body(file_path: str) -> str | None:
        path = Path(file_path)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return str(payload.get("content") or "")
        except (OSError, json.JSONDecodeError, TypeError):
            return None

    def _attach_thumbnail(self, material: Material) -> None:
        if material.type != "image":
            return
        storage = self.factory.get_storage_adapter()
        thumb_path = generate_image_thumbnail(material.file_path, storage)
        if thumb_path:
            material.thumbnail = thumb_path

    def get(self, material_id: int) -> Material | None:
        return self.db.query(Material).filter(Material.id == material_id, Material.status == "active").first()

    def get_any(self, material_id: int) -> Material | None:
        return self.db.query(Material).filter(Material.id == material_id).first()

    def delete_material(self, material_id: int) -> None:
        material = self.get(material_id)
        if not material:
            raise ValueError("素材不存在")
        material.status = "deleted"
        self.db.commit()

    def list_materials(
        self,
        material_type: str | None = None,
        category: str | None = None,
        keyword: str | None = None,
    ) -> list[Material]:
        query = self.db.query(Material).filter(Material.status == "active")
        if material_type:
            query = query.filter(Material.type == material_type)
        if category:
            query = query.filter(Material.category == category)
        if keyword:
            like = f"%{keyword}%"
            query = query.filter(
                (Material.name.like(like)) | (Material.file_path.like(like))
            )
        return query.order_by(Material.id.desc()).all()

    def list_categories(self) -> list[str]:
        rows = (
            self.db.query(Material.category)
            .filter(Material.status == "active", Material.category.isnot(None), Material.category != "")
            .distinct()
            .all()
        )
        return sorted({row[0] for row in rows if row[0]})

    async def upload(
        self,
        file: UploadFile,
        user_id: int | None = None,
        name: str | None = None,
        category: str | None = None,
    ) -> Material:
        suffix = Path(file.filename or "upload.bin").suffix or ".bin"
        content = await file.read()
        material_type = "video" if suffix.lower() in {".mp4", ".mov", ".avi"} else "image"
        storage = self.factory.get_storage_adapter()
        file_path, url = storage.save_bytes(content, suffix=suffix)
        material = Material(
            type=material_type,
            source="upload",
            file_path=file_path,
            url=url,
            name=name or Path(file.filename or "upload").stem,
            category=category or "默认",
            created_by=user_id,
        )
        self._attach_thumbnail(material)
        self.db.add(material)
        self.db.commit()
        self.db.refresh(material)
        if material.type == "image":
            await ImageModerationService(self.db).apply_to_material(material)
            self.db.commit()
            self.db.refresh(material)
        return material

    def save_text_draft(
        self,
        *,
        title: str,
        content: str,
        tags: list[str] | None = None,
        platform: str = "xhs",
        comment_guide: str | None = None,
        topic: str | None = None,
        category: str | None = None,
        user_id: int | None = None,
        ai_record_id: int | None = None,
    ) -> Material:
        payload = {
            "title": title,
            "content": content,
            "tags": tags or [],
            "platform": platform,
            "comment_guide": comment_guide,
            "topic": topic,
        }
        storage = self.factory.get_storage_adapter()
        file_path, _ = storage.save_bytes(
            json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            suffix=".json",
        )
        material = Material(
            type="text",
            source="draft",
            file_path=file_path,
            name=_safe_material_name(title),
            category=category or "文案草稿",
            ai_record_id=ai_record_id,
            created_by=user_id,
        )
        self.db.add(material)
        self.db.commit()
        self.db.refresh(material)
        return material

    def create_from_ai_paths(
        self,
        image_paths: list[str],
        ai_record_id: int | None = None,
        user_id: int | None = None,
    ) -> list[Material]:
        storage = self.factory.get_storage_adapter()
        materials: list[Material] = []
        for path in image_paths:
            material = Material(
                type="image",
                source="ai_generated",
                file_path=path,
                url=storage.get_url(path),
                ai_record_id=ai_record_id,
                created_by=user_id,
            )
            self._attach_thumbnail(material)
            self.db.add(material)
            materials.append(material)
        self.db.commit()
        for material in materials:
            self.db.refresh(material)
        return materials

    def validate_material_ids(self, material_ids: list[int], content_type: str) -> list[Material]:
        materials = []
        for material_id in material_ids:
            material = self.get(material_id)
            if not material:
                raise ValueError(f"素材不存在: {material_id}")
            if content_type == "note" and material.type != "image":
                raise ValueError(f"图文任务需要图片素材: {material_id}")
            if content_type == "video" and material.type not in {"video", "image"}:
                raise ValueError(f"视频任务素材类型无效: {material_id}")
            materials.append(material)
        if content_type == "video" and not any(m.type == "video" for m in materials):
            raise ValueError("视频任务需要至少一个视频素材")
        ImageModerationService(self.db).assert_images_allowed(materials)
        return materials


class AiContentService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.factory = get_adapter_factory()
        self.material_service = MaterialService(db)

    def _resolve_avatar_reference_image(self, avatar_id: int) -> str | None:
        """从 Avatar 的 reference_images 解析出第一张参考图的 URL。"""
        avatar = self.db.query(Avatar).filter(Avatar.id == avatar_id, Avatar.status == "active").first()
        if not avatar or not avatar.reference_images:
            return None
        ref_ids = avatar.reference_images
        if not isinstance(ref_ids, list) or not ref_ids:
            return None
        # reference_images 存的是素材 ID 列表，取第一张
        first_id = ref_ids[0]
        mat = self.db.query(Material).filter(Material.id == first_id, Material.status == "active").first()
        if mat and mat.url:
            return mat.url
        if mat and mat.file_path:
            storage = self.factory.get_storage_adapter()
            return storage.get_url(mat.file_path)
        return None

    async def generate_text(
        self,
        topic: str,
        platform: str,
        user_id: int | None = None,
        content_type: str = "note",
    ) -> dict:
        adapter = self.factory.get_ai_text_adapter()
        result = await adapter.generate(
            TextGenerateInput(topic=topic, platform=platform, content_type=content_type)
        )
        record = AiGenerationRecord(
            type="text",
            provider=result.provider,
            prompt=result.prompt,
            result_summary=f"title={result.title}",
            cost=result.cost,
            created_by=user_id,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return {
            "record_id": record.id,
            "title": result.title,
            "content": result.content,
            "tags": result.tags,
            "cover_text": result.cover_text,
            "comment_guide": result.comment_guide,
            "provider": result.provider,
            "model": getattr(adapter, "model", None),
            "cost": float(result.cost),
        }

    async def generate_image(
        self,
        topic: str,
        platform: str,
        ratio: str = "3:4",
        count: int = 1,
        cover_text: str | None = None,
        user_id: int | None = None,
        *,
        style: str = "default",
        brand_color: str | None = None,
        brand_hint: str | None = None,
    ) -> dict:
        adapter = self.factory.get_ai_image_adapter()
        result = await adapter.generate(
            ImageGenerateInput(
                topic=topic,
                platform=platform,
                ratio=ratio,
                count=count,
                cover_text=cover_text,
                style=style,
                brand_color=brand_color,
                brand_hint=brand_hint,
            )
        )
        import json

        record = AiGenerationRecord(
            type="image",
            provider=result.provider,
            prompt=result.prompt,
            result_summary=json.dumps(
                {
                    "images": len(result.image_paths),
                    "style": style,
                    "ratio": ratio,
                    "brand_color": brand_color,
                    "brand_hint": brand_hint,
                    "negative_prompt": result.negative_prompt,
                },
                ensure_ascii=False,
            ),
            cost=result.cost,
            created_by=user_id,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        materials = self.material_service.create_from_ai_paths(
            result.image_paths,
            ai_record_id=record.id,
            user_id=user_id,
        )
        moderation = ImageModerationService(self.db)
        for material in materials:
            await moderation.apply_to_material(material)
        self.db.commit()
        for material in materials:
            self.db.refresh(material)
        return {
            "record_id": record.id,
            "materials": [{"id": m.id, "url": m.url, "file_path": m.file_path} for m in materials],
            "provider": result.provider,
            "model": getattr(adapter, "model", None),
            "prompt": result.prompt,
            "style": style,
            "brand_color": brand_color,
            "brand_hint": brand_hint,
            "cost": float(result.cost),
            "elapsed": float(getattr(result, "elapsed", 0.0)),
        }

    async def generate_video(
        self,
        topic: str,
        platform: str,
        duration: int,
        resolution: str,
        fps: int,
        image_url: str | None,
        user_id: int | None = None,
        avatar_id: int | None = None,
        avatar_type: str | None = None,
        voice_id: str | None = None,
        tts_text: str | None = None,
    ) -> dict:
        """AI 视频生成核心逻辑"""
        # 数字人 / 仿真人 → 腾讯云 VOD AIGC (Kling)
        # 数字人: avatar_i2v + 参考图; 仿真人: lip_sync + 参考视频 + 文案
        scene_type: str | None = None
        reference_image_url: str | None = None
        reference_video_url: str | None = None
        reference_audio_url: str | None = None
        script_text: str | None = None
        subject_image_url: str | None = None  # 用于腾讯云主体注册的干净原图（数字人）
        avatar_subject_id: str | None = None   # 已缓存的腾讯云主体 ID（命中则跳过注册）

        if avatar_type in ("simulation_human", "digital_human") and avatar_id:
            avatar = self.db.query(Avatar).filter(Avatar.id == avatar_id, Avatar.status == "active").first()
            if not avatar:
                raise ValueError(f"Avatar(id={avatar_id}) 不存在或已删除")
            if avatar.type == "digital_human":
                scene_type = "avatar_i2v"
                # 数字人读取参考图 URL（avatar_i2v 场景必填，不能为空）
                # 若已生成「带背景参考图」(background_image_url)，优先用作驱动图，让视频带背景
                storage = self.factory.get_storage_adapter()
                background_url = getattr(avatar, "background_image_url", None)
                # 统一过 storage.get_url 规范化成 "/static/materials/xxx"，
                # 兼容历史脏数据：DB 里可能存的是容器内绝对路径 (/data/materials/xxx)
                # 或文件名，storage.get_url 都按 basename 归一，保证 FastAPI 的
                # /static/materials 路由可访问、腾讯云能公网拉取。
                if background_url:
                    reference_image_url = storage.get_url(background_url)
                else:
                    reference_image_url = (
                        storage.get_url(avatar.reference_image_url)
                        if avatar.reference_image_url
                        else None
                    )
                if not reference_image_url:
                    raise ValueError(
                        f"数字人 Avatar(id={avatar_id}) 未配置参考图（reference_image_url），无法生成。"
                    )
                # 主体注册：用干净的数字人原图（reference_image_url，而非带背景杂物
                # 的 background_image_url）作为主体，让 Kling 只驱动人脸、背景不漂移。
                if avatar.reference_image_url:
                    subject_image_url = storage.get_url(avatar.reference_image_url)
                # 复用已缓存的主体 ID，避免重复注册
                avatar_subject_id = getattr(avatar, "subject_id", None)
            elif avatar.type == "simulation_human":
                scene_type = "lip_sync"
                # 同样过 storage.get_url 规范化参考视频路径
                storage = self.factory.get_storage_adapter()
                reference_video_url = (
                    storage.get_url(avatar.reference_video_url)
                    if avatar.reference_video_url
                    else None
                )
                if not reference_video_url:
                    raise ValueError(
                        f"仿真人 Avatar(id={avatar_id}) 未配置参考视频（reference_video_url），无法生成。"
                    )
                # 仿真人文案默认用 topic（前端已把 final_copy.body 作为 topic 传入）
                script_text = topic
        elif avatar_type == "digital_human":
            scene_type = "avatar_i2v"
        elif avatar_type == "simulation_human":
            scene_type = "lip_sync"

        # ====== 数字人 / 仿真人：TTS 合成真实口播音频 ======
        # 原 placeholder_silence.wav（440Hz 正弦波）会触发 Kling 自带乱码字幕
        # + 口型无法对齐；改用 edge-tts 合成的真实普通话 mp3 喂给 Kling。
        generated_audio_url: str | None = None
        tts_voice_used: str | None = None
        audio_duration: float = 0.0
        audio_local_path: str | None = None
        if scene_type in ("avatar_i2v", "lip_sync"):
            try:
                from app.utils.tts import synthesize_speech, resolve_voice_id

                # 实际要念的文本：优先 tts_text > script_text > topic
                speak_text = (tts_text or script_text or topic or "").strip()
                if speak_text:
                    # 不再截断：数字人视频时长 = 音频时长，
                    # tts 内部会按句分段合成拼接，避免长文本卡顿且口播完整。
                    effective_voice = resolve_voice_id(voice_id)
                    tts_result = synthesize_speech(
                        text=speak_text,
                        voice_id=effective_voice,
                        prefix="avatar",
                    )
                    generated_audio_url = tts_result.audio_url
                    tts_voice_used = tts_result.voice_id
                    reference_audio_url = tts_result.audio_url
                    audio_duration = tts_result.duration_sec
                    audio_local_path = tts_result.audio_path
                    logger.info(
                        "TTS 合成成功: voice=%s, bytes=%d, est_duration=%.2fs, text_len=%d, url=%s, abs_url=%s",
                        tts_voice_used,
                        tts_result.file_size,
                        tts_result.duration_sec,
                        len(speak_text),
                        tts_result.audio_url,
                        self._abs_audio_url(tts_result.audio_url),
                    )
            except Exception as e:  # TTS 失败时降级到 placeholder，不阻断流程
                logger.warning("TTS 合成失败，降级为静音 wav: %s", e)

        # 仿真人/数字人统一走腾讯云 VOD AIGC（Kling）
        if scene_type:
            adapter = self.factory.get_ai_video_adapter()
        else:
            adapter = self.factory.get_ai_video_adapter()

        video_input = VideoGenerateInput(
            topic=topic,
            platform=platform,
            duration=duration,
            resolution=resolution,
            fps=fps,
            image_url=image_url,
            avatar_id=avatar_id,
            avatar_type=avatar_type,
            scene_type=scene_type,
            reference_image_url=reference_image_url,
            reference_video_url=reference_video_url,
            reference_audio_url=reference_audio_url,
            script_text=script_text,
            subject_image_url=subject_image_url,
            avatar_subject_id=avatar_subject_id,
            voice_id=tts_voice_used or voice_id,
            tts_text=tts_text or script_text or topic,
            audio_duration=audio_duration,
        )

        logger.info(
            "开始 AI 视频生成: topic=%s, duration=%s, resolution=%s, adapter=%s",
            topic,
            duration,
            resolution,
            getattr(adapter, "provider", type(adapter).__name__),
        )

        # 调用适配器生成
        result = await adapter.generate(video_input)

        # 把适配器新注册的主体 ID 缓存回 Avatar，避免后续重复注册
        new_subject_id = (result.metadata or {}).get("subject_id") if result.metadata else None
        if new_subject_id and avatar_id and avatar_type == "digital_human":
            cached = self.db.query(Avatar).filter(Avatar.id == avatar_id).first()
            if cached and not cached.subject_id:
                cached.subject_id = new_subject_id
                self.db.flush()

        logger.info(
            "AI 视频生成完成: videos=%s, thumbnails=%s, provider=%s, elapsed=%s",
            result.video_paths,
            result.thumbnail_paths,
            result.provider,
            result.elapsed,
        )

        # 记录 AI 调用日志
        import json

        record = AiGenerationRecord(
            type="video",
            provider=result.provider,
            prompt=result.prompt,
            result_summary=json.dumps(
                {
                    "videos": len(result.video_paths),
                    "duration": result.duration,
                    "resolution": resolution,
                    "fps": fps,
                    "model": result.metadata.get("model") if result.metadata else None,
                },
                ensure_ascii=False,
            ),
            cost=result.cost,
            created_by=user_id,
        )
        self.db.add(record)
        self.db.flush()

        # 创建视频素材记录
        materials = []
        storage = self.factory.get_storage_adapter()

        # 数字人 / 仿真人：把已知口播文本按音频时长烧录字幕（硬字幕，下载即带字幕）
        burn_sub_enabled = avatar_type in ("digital_human", "simulation_human")
        # 字幕文本来源需与 TTS 口播文本保持一致（tts_text > script_text > topic），
        # 否则会出现「TTS 能念字、字幕却是空」的不一致（此前仅用 tts_text 导致缺字幕）。
        subtitle_text = (tts_text or script_text or topic or "").strip()
        subtitle_total_dur = audio_duration if audio_duration and audio_duration > 0 else (result.duration or 0.0)

        for idx, (video_path, thumb_path) in enumerate(zip(result.video_paths, result.thumbnail_paths)):
            final_video_path = video_path
            try:
                if burn_sub_enabled and subtitle_text and os.path.exists(video_path):
                    from app.utils.subtitle import burn_subtitles
                    burned = burn_subtitles(
                        video_path, subtitle_text, subtitle_total_dur, fontsize=28
                    )
                    if burned and os.path.exists(burned):
                        final_video_path = burned
                        logger.info(
                            "[字幕] 烧录成功: %s -> %s", video_path, burned
                        )
                    else:
                        logger.warning("[字幕] 烧录失败，保留原视频: %s", video_path)
            except Exception as e:
                logger.warning("[字幕] 烧录异常，保留原视频: %s", e)

            video_url = storage.get_url(final_video_path)

            material = Material(
                created_by=user_id,
                name=_safe_material_name(f"{topic}_视频_{idx + 1}"),
                type="video",
                source="ai_generated",
                file_path=final_video_path,
                url=video_url,
                thumbnail=thumb_path,
                ai_record_id=record.id,
            )
            self.db.add(material)
            materials.append(material)

        # 保存 TTS 真实口播音频为素材，方便在素材库直接试听、确认音频质量
        if audio_local_path and os.path.exists(audio_local_path):
            try:
                audio_material = Material(
                    created_by=user_id,
                    name=_safe_material_name(f"{topic}_口播音频"),
                    type="audio",
                    source="tts_generated",
                    file_path=audio_local_path,
                    url=storage.get_url(audio_local_path) if storage else None,
                    ai_record_id=record.id,
                )
                self.db.add(audio_material)
                logger.info(
                    "口播音频素材已保存: path=%s, duration=%.2fs",
                    audio_local_path,
                    audio_duration,
                )
            except Exception as e:
                logger.warning("保存口播音频素材失败(不影响视频生成): %s", e)

        self.db.commit()

        for material in materials:
            self.db.refresh(material)

        return {
            "record_id": record.id,
            "materials": [
                {
                    "id": m.id,
                    "url": m.url,
                    "thumbnail_url": storage.get_url(m.thumbnail) if m.thumbnail else None,
                    "duration": result.duration,
                }
                for m in materials
            ],
            "provider": result.provider,
            "model": getattr(adapter, "model", None),
            "prompt": result.prompt,
            "cost": float(result.cost),
            "elapsed": float(getattr(result, "elapsed", 0.0)),
        }

