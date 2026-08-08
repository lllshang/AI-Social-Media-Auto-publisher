"""内容创作服务 — 灵感输入 → 文案创作+润色 → 内容生成 → 定稿入库"""

from __future__ import annotations

import json
import logging
import asyncio
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# 全局生成并发信号量：腾讯云 VOD AIGC 同账号短时间内并发极易触发
# RequestLimitExceeded（ErrCode 70000）。设为 1 强制串行，避免连点两次时
# 两个任务同时打腾讯云导致限流失败。
# 放在模块级，保证所有 CreateService 实例共享同一个 Semaphore。
GENERATION_SEMAPHORE = asyncio.Semaphore(1)


def _log_task_exception(task):
    """asyncio.create_task 的 done_callback：捕获后台 task 异常避免静默丢失。"""
    try:
        exc = task.exception()
        if exc is not None:
            logger.exception("后台异步任务异常未捕获", exc_info=exc)
    except (asyncio.CancelledError, Exception):  # noqa: BLE001
        pass


from sqlalchemy.orm import Session

from app.models import CreativeSession, GenerationTask, Material, AiGenerationRecord
from app.schemas import (
    CopyResponse,
    CreativeSessionCreate as SessionCreateData,
    GenerationRequest as GenRequestData,
    PolishRequest,
    PolishResponse,
    SaveDraftRequest,
)


# ── 快捷润色动作映射 ─────────────────────────────────────────────

QUICK_ACTIONS: dict[str, str] = {
    "shorten": "请将文案缩短到原来的一半以内，保留核心信息",
    "expand": "请将文案扩写，增加更多细节和感情描述",
    "humorous": "请让文案更幽默有趣，增加网络热梗",
    "add_emoji": "请在合适位置添加适量的 emoji 表情",
    "formal": "请让文案更正式专业，减少口语化表达",
    "bilibili_style": "请调整为B站风格：口语化、有梗、二次元感、适合年轻受众",
    "xiaohongshu_style": "请调整为小红书风格：种草感、生活化、加emoji、分段落、标感叹号",
    "douyin_style": "请调整为抖音风格：短平快、有悬念、引导互动、加话题标签",
}


class CreateService:
    """内容创作服务"""

    def __init__(self, db: Session):
        self.db = db

    # ── 会话管理 ────────────────────────────────────────────────

    def create_session(self, user_id: int, data: SessionCreateData) -> CreativeSession:
        session = CreativeSession(
            user_id=user_id,
            content_type=data.content_type,
            keywords=data.keywords,
            background=data.background,
            theme_style=data.theme_style,
            scene_desc=data.scene_desc,
            platforms=data.platforms or [],
            status="drafting",
            polish_history=[],
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_session(self, session_id: int, user_id: int) -> CreativeSession | None:
        return (
            self.db.query(CreativeSession)
            .filter(CreativeSession.id == session_id, CreativeSession.user_id == user_id)
            .first()
        )

    def get_sessions(
        self, user_id: int, page: int = 1, page_size: int = 20
    ) -> tuple[list[CreativeSession], int]:
        q = self.db.query(CreativeSession).filter(CreativeSession.user_id == user_id)
        total = q.count()
        items = q.order_by(CreativeSession.updated_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
        # 给每个 session 注入 generation_count 字段，供 UI 判断"该草稿是否有生成任务"
        # 这样前端恢复草稿时能直接决定跳到哪一步，无需在 list 阶段就拉每个 session 的任务列表
        for it in items:
            it.generation_count = (
                self.db.query(GenerationTask).filter(GenerationTask.session_id == it.id).count()
            )
        return items, total

    def delete_session(self, session_id: int, user_id: int) -> bool:
        session = self.get_session(session_id, user_id)
        if not session:
            return False
        # 删除关联的生成任务
        self.db.query(GenerationTask).filter(GenerationTask.session_id == session_id).delete()
        self.db.delete(session)
        self.db.commit()
        return True

    # ── 文案生成与润色 ──────────────────────────────────────────

    async def generate_copy(self, session_id: int, user_id: int) -> CopyResponse:
        """根据会话输入参数，调用 AI 生成文案初稿"""
        session = self._require_session(session_id, user_id)

        from app.services.ai_model_service import AiModelService
        from app.services.material_service import AiContentService

        svc = AiContentService(self.db)
        model_svc = AiModelService()

        detection = await model_svc.detect_all()
        text_config = detection.text["current"]
        provider = text_config.get("provider", "tongyi")
        model = text_config.get("model", "qwen-plus")

        # 选择平台风格（取第一个平台，或默认 xhs）
        platform = session.platforms[0] if session.platforms else "xhs"

        # 构建 prompt
        prompt_parts = [f"关键词：{session.keywords}"]
        if session.background:
            prompt_parts.append(f"背景信息：{session.background}")
        if session.theme_style:
            prompt_parts.append(f"主题/风格：{session.theme_style}")
        if session.scene_desc:
            prompt_parts.append(f"场景描述：{session.scene_desc}")
        prompt_parts.append(f"请根据以上信息，为{platform}平台生成一篇完整的营销文案，包含标题、正文和3-5个标签。")
        if session.content_type == "video":
            prompt_parts.append("文案应适合视频口播场景。")
        final_prompt = "\n".join(prompt_parts)

        try:
            result = await svc.generate_text(
                topic=final_prompt,
                platform=platform,
                content_type=session.content_type,
            )
            title = result.get("title", "")
            body = result.get("content", "") or result.get("body", "")
            tags = result.get("tags", [])

            if not body and isinstance(result, str):
                body = result

            copy_data = {"title": title, "body": body, "tags": tags}
        except Exception:
            # 降级：返回一个占位初稿
            copy_data = {
                "title": session.keywords[:50],
                "body": f"根据关键词「{session.keywords}」生成的初始文案，请通过润色完善内容。",
                "tags": [session.keywords.replace(" ", "")[:10]],
            }

        session.final_copy = copy_data
        session.updated_at = datetime.utcnow()
        self.db.commit()

        return CopyResponse(**copy_data)

    async def polish_copy(
        self, session_id: int, user_id: int, req: PolishRequest
    ) -> PolishResponse:
        """对话式润色：基于当前文案 + 用户指令，返回润色结果"""
        session = self._require_session(session_id, user_id)

        if not session.final_copy:
            return PolishResponse(title="", body="（请先生成初稿文案）", tags=[])

        current = session.final_copy

        # 解析润色指令
        if req.quick_action and req.quick_action in QUICK_ACTIONS:
            instruction = QUICK_ACTIONS[req.quick_action]
        elif req.message:
            instruction = req.message
        else:
            instruction = "请润色优化此文案"

        # 记录历史
        history = session.polish_history or []
        if req.quick_action:
            history.append({"role": "user", "content": f"[{req.quick_action}]"})
        else:
            history.append({"role": "user", "content": req.message or ""})

        # 构建润色 prompt
        platform = session.platforms[0] if session.platforms else "xhs"
        prompt = f"""当前文案：
标题：{current.get('title', '')}
正文：{current.get('body', '')}
标签：{', '.join(current.get('tags', []))}

润色指令：{instruction}

请根据指令改写文案，保持与目标平台{platform}风格一致。返回格式：
标题：xxx
正文：xxx
标签：#tag1 #tag2"""

        from app.services.ai_model_service import AiModelService
        from app.services.material_service import AiContentService

        svc = AiContentService(self.db)

        try:
            result = await svc.generate_text(
                topic=prompt,
                platform=platform,
                content_type=session.content_type,
            )
            title = result.get("title", current.get("title", ""))
            body = result.get("content", "") or result.get("body", "")
            if not body and isinstance(result, str):
                body = result
            tags = result.get("tags", current.get("tags", []))

            copy_data = {"title": title, "body": body, "tags": tags}
        except Exception:
            # 润色失败则保留当前文案
            copy_data = dict(current)

        # 更新文案
        session.final_copy = copy_data
        history.append({"role": "assistant", "content": f"已根据「{instruction}」润色"})
        session.polish_history = history
        session.updated_at = datetime.utcnow()
        self.db.commit()

        return PolishResponse(**copy_data)

    def update_copy(self, session_id: int, user_id: int, data: dict) -> CopyResponse:
        """内联编辑：直接保存用户手动修改"""
        session = self._require_session(session_id, user_id)

        current = dict(session.final_copy or {})
        if data.get("title") is not None:
            current["title"] = data["title"]
        if data.get("body") is not None:
            current["body"] = data["body"]
        if data.get("tags") is not None:
            current["tags"] = data["tags"]

        session.final_copy = current
        session.updated_at = datetime.utcnow()
        self.db.commit()

        return CopyResponse(**current)

    def get_copy(self, session_id: int, user_id: int) -> CopyResponse:
        session = self._require_session(session_id, user_id)
        if not session.final_copy:
            return CopyResponse(title="", body="（尚未生成文案）", tags=[])
        return CopyResponse(**session.final_copy)

    # ── 内容生成 ────────────────────────────────────────────────

    async def start_generation(
        self, session_id: int, user_id: int, data: GenRequestData
    ) -> GenerationTask:
        """触发异步内容生成（视频或图文）"""
        session = self._require_session(session_id, user_id)

        task = GenerationTask(
            session_id=session_id,
            gen_type=data.gen_type,
            provider="pending",
            input_params=data.model_dump(),
            status="pending",
            progress=0,
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)

        # 启动异步生成
        self.db.expunge(task)
        # session 是 self.db 附着的 ORM 对象，跨 event loop 后再访问会
        # DetachedInstanceError。提前把需要的字段抠出来传给后台 task。
        import asyncio
        session_snapshot = {
            "platforms": list(session.platforms or []),
            "user_id": session.user_id,
            "final_copy": session.final_copy,
            "keywords": session.keywords,
            "theme_style": session.theme_style,
        }
        _task_handle = asyncio.create_task(
            self._execute_generation(task.id, session_snapshot, data)
        )
        # 捕获 task 异常，避免 "Task exception was never retrieved"
        _task_handle.add_done_callback(_log_task_exception)

        # 重新查询以获取最新状态
        session.status = "generating"
        session.updated_at = datetime.utcnow()
        self.db.commit()

        # 返回最新的 task
        return self.db.query(GenerationTask).filter(GenerationTask.id == task.id).first()

    async def _execute_generation(
        self, task_id: int, session_snapshot: dict, data: GenRequestData
    ):
        """后台执行生成任务。
        session_snapshot 是 dict 快照（不再传 ORM 对象），避免
        DetachedInstanceError。
        """
        from app.database import SessionLocal

        # 新 db session 用于后台任务
        bg_db = SessionLocal()
        try:
            logger.info(f"[gen:{task_id}] 开始后台执行任务, gen_type={data.gen_type}")
            task = bg_db.query(GenerationTask).filter(GenerationTask.id == task_id).first()
            if not task:
                logger.warning(f"[gen:{task_id}] 未找到任务, 直接退出")
                return

            task.status = "running"
            task.progress = 10
            bg_db.commit()
            logger.info(f"[gen:{task_id}] 任务状态更新为 running/10%")

            # 全局并发限流：等待拿到信号量后再真正调用第三方 AIGC，
            # 避免同账号并发过高触发 RequestLimitExceeded。
            # 在排队期间也持续更新 progress，让前端轮询能看到"等待中"而不是卡在 10%。
            logger.info(f"[gen:{task_id}] 等待生成并发信号量 (可用={GENERATION_SEMAPHORE._value})")
            # 先把进度改成 3% 表示"排队等待并发槽位"
            task.progress = 3
            bg_db.commit()
            async with GENERATION_SEMAPHORE:
                logger.info(f"[gen:{task_id}] 获得生成并发信号量，开始调用第三方 AIGC")
                # 拿到信号量后立刻把进度推进到 20%，让前端感知到状态变化
                task.progress = 20
                task.status = "running"
                bg_db.commit()
                if data.gen_type in ("text_to_video", "image_to_video", "simulation_human", "digital_human"):
                    logger.info(f"[gen:{task_id}] 进入视频生成分支")
                    result = await self._generate_video_for_task(bg_db, task, session_snapshot, data)
                elif data.gen_type in ("cover", "images"):
                    logger.info(f"[gen:{task_id}] 进入图片生成分支")
                    result = await self._generate_images_for_task(bg_db, task, session_snapshot, data)
                else:
                    raise ValueError(f"Unknown gen_type: {data.gen_type}")

            logger.info(f"[gen:{task_id}] 生成完成, result={result}")
            task.status = "completed"
            task.progress = 100
            task.result = result
            task.completed_at = datetime.utcnow()
            bg_db.commit()
            logger.info(f"[gen:{task_id}] 任务状态更新为 completed/100%")

        except Exception as exc:
            # 前台/后台任务中若 DB 写入失败（如字段超长），session 可能已进入
            # PendingRollback 状态，必须先 rollback 才能写入失败状态，否则会二次
            # 抛异常导致任务永远停在 10%（"Task exception was never retrieved"）。
            try:
                bg_db.rollback()
            except Exception:
                pass
            try:
                task = bg_db.query(GenerationTask).filter(GenerationTask.id == task_id).first()
                if task:
                    task.status = "failed"
                    task.error_message = str(exc)
                    task.completed_at = datetime.utcnow()
                    bg_db.commit()
            except Exception as commit_exc:
                logger.error(f"[gen:{task_id}] 更新生成任务失败状态失败: {commit_exc}")
                logger.exception(f"[gen:{task_id}] 生成任务异常", exc_info=exc)
        finally:
            bg_db.close()

    async def _generate_video_for_task(
        self, db: Session, task: GenerationTask, session_snapshot: dict, data: GenRequestData
    ) -> dict:
        """执行视频生成"""
        from app.services.material_service import AiContentService

        svc = AiContentService(db)

        platforms = session_snapshot.get("platforms") or []
        platform = platforms[0] if platforms else "douyin"
        final_copy = session_snapshot.get("final_copy") or {}
        description = data.description or ""
        if not description and final_copy:
            # 不再截断：数字人视频时长由音频驱动，TTS 内部按句分段合成拼接，
            # 完整文案都能被念出来（最长约 300s）。
            description = f"{final_copy.get('title', '')} {final_copy.get('body', '')}".strip()

        result = await svc.generate_video(
            topic=description,
            platform=platform,
            duration=data.duration,
            resolution=data.resolution,
            fps=data.fps,
            image_url=data.image_url,
            user_id=session_snapshot.get("user_id"),
            avatar_id=data.avatar_id,
            avatar_type=data.avatar_type,
            voice_id=data.voice_id,
            tts_text=data.tts_text,
        )

        task.provider = result.get("provider", "unknown")
        db.commit()

        material_ids = [m["id"] for m in result.get("materials", [])]
        # Video URL: 优先顶层 video_url；否则取第一个 material 的 url
        _video_url = result.get("video_url")
        if not _video_url and result.get("materials"):
            _video_url = result["materials"][0].get("url")
        # 视频生成不产生图片，image_urls 固定为空，避免误把 mp4 当图片
        return {
            "material_ids": material_ids,
            "video_url": _video_url,
            "image_urls": [],
            "provider": result.get("provider"),
        }

    async def _generate_images_for_task(
        self, db: Session, task: GenerationTask, session_snapshot: dict, data: GenRequestData
    ) -> dict:
        """执行图片/封面生成"""
        from app.services.material_service import AiContentService

        svc = AiContentService(db)

        platforms = session_snapshot.get("platforms") or []
        platform = platforms[0] if platforms else "xhs"
        description = data.description or session_snapshot.get("keywords") or ""

        result = await svc.generate_image(
            topic=description,
            platform=platform,
            style=data.style or session_snapshot.get("theme_style") or "default",
            ratio="3:4",
            count=data.count,
            cover_text=data.cover_text,
            brand_color=data.brand_color,
            brand_hint=data.brand_hint,
            user_id=session_snapshot.get("user_id"),
        )

        task.provider = result.get("provider", "unknown")
        db.commit()

        material_ids = [m["id"] for m in result.get("materials", [])]
        _image_urls = [m.get("url") for m in result.get("materials", []) if m.get("url")]
        return {
            "material_ids": material_ids,
            "image_urls": _image_urls,
            "provider": result.get("provider"),
        }

    def get_generations(
        self, session_id: int, user_id: int
    ) -> list[GenerationTask]:
        self._require_session(session_id, user_id)
        return (
            self.db.query(GenerationTask)
            .filter(GenerationTask.session_id == session_id)
            .order_by(GenerationTask.created_at.desc())
            .all()
        )

    def get_generation(self, gen_id: int, user_id: int) -> GenerationTask | None:
        task = self.db.query(GenerationTask).filter(GenerationTask.id == gen_id).first()
        if not task:
            return None
        # 验证所有权
        session = self.db.query(CreativeSession).filter(
            CreativeSession.id == task.session_id,
            CreativeSession.user_id == user_id,
        ).first()
        if not session:
            return None
        return task

    # ── 完成创作 ────────────────────────────────────────────────

    def complete_session(self, session_id: int, user_id: int) -> list[dict]:
        """完成创作：定稿文案 + 选定素材入库，标记完成"""
        session = self._require_session(session_id, user_id)

        from app.services.material_service import MaterialService

        mat_svc = MaterialService(self.db)
        output_ids = []

        # 保存定稿文案为素材
        if session.final_copy:
            text_mat = mat_svc.save_text_draft(
                title=session.final_copy.get("title", session.keywords[:50]),
                content=session.final_copy.get("body", ""),
                tags=session.final_copy.get("tags", []),
                platform=session.platforms[0] if session.platforms else "xhs",
                user_id=session.user_id,
            )
            if text_mat:
                output_ids.append(text_mat.id)

        # 关联已完成的生成任务素材
        completed_generations = (
            self.db.query(GenerationTask)
            .filter(
                GenerationTask.session_id == session_id,
                GenerationTask.status == "completed",
            )
            .all()
        )
        for gen in completed_generations:
            if gen.result and gen.result.get("material_ids"):
                for mid in gen.result["material_ids"]:
                    if mid not in output_ids:
                        # 标记为创作产出
                        mat = self.db.query(Material).filter(Material.id == mid).first()
                        if mat:
                            mat.category = "创作产出"
                            output_ids.append(mid)

        self.db.commit()

        session.output_material_ids = output_ids
        session.status = "completed"
        session.updated_at = datetime.utcnow()
        self.db.commit()

        return [{"id": mid} for mid in output_ids]

    # ── 草稿保存 ────────────────────────────────────────────────

    def save_draft(self, session_id: int, user_id: int, data: SaveDraftRequest):
        """保存创作草稿（页面离开时调用）"""
        session = self._require_session(session_id, user_id)

        draft = {}
        if data.step is not None:
            draft["step"] = data.step
        if data.form is not None:
            draft["form"] = data.form
        if data.copy_data is not None:
            draft["copy"] = data.copy_data
        if data.video_params is not None:
            draft["video_params"] = data.video_params
        if data.image_params is not None:
            draft["image_params"] = data.image_params

        # 合并已有 draft_data（防止覆盖未提供的字段）
        if session.draft_data:
            existing = dict(session.draft_data)
            existing.update(draft)
            draft = existing

        session.draft_data = draft
        session.updated_at = datetime.utcnow()
        self.db.commit()

    def get_drafting_sessions(
        self, user_id: int
    ) -> list[CreativeSession]:
        """获取未完成的创作会话（可恢复的草稿）"""
        return (
            self.db.query(CreativeSession)
            .filter(
                CreativeSession.user_id == user_id,
                CreativeSession.status.in_(["drafting", "generating"]),
            )
            .order_by(CreativeSession.updated_at.desc())
            .all()
        )

    # ── 内部辅助 ────────────────────────────────────────────────

    def _require_session(self, session_id: int, user_id: int) -> CreativeSession:
        session = self.get_session(session_id, user_id)
        if not session:
            raise ValueError("创作会话不存在或无权访问")
        return session
