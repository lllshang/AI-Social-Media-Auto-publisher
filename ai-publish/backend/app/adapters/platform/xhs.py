import asyncio
import sys
from pathlib import Path

from loguru import logger

from app.adapters.base import LoginResult, PublishContext, PublishResult
from app.config import get_settings
from app.utils.runtime_env import format_vendor_import_error


class XhsPlatformAdapter:
    platform = "xhs"

    def __init__(self) -> None:
        self.settings = get_settings()
        self._ensure_vendor_path()

    def _ensure_vendor_path(self) -> None:
        vendor = Path(self.settings.sau_vendor_path).resolve()
        if vendor.exists() and str(vendor) not in sys.path:
            sys.path.insert(0, str(vendor))

    def _configure_vendor_conf(self) -> None:
        vendor = Path(self.settings.sau_vendor_path).resolve()
        if not vendor.exists():
            return
        try:
            import conf  # type: ignore

            conf.LOCAL_CHROME_HEADLESS = self.settings.playwright_headless
            from app.utils.playwright_browser import find_chromium_executable

            chrome_path = find_chromium_executable()
            if chrome_path:
                conf.LOCAL_CHROME_PATH = chrome_path
        except Exception as exc:
            logger.warning("Configure vendor conf skipped: {}", exc)

    def _import_vendor(self):
        self._ensure_vendor_path()
        self._configure_vendor_conf()
        vendor = Path(self.settings.sau_vendor_path).resolve()
        if not vendor.exists():
            raise RuntimeError(
                f"未找到 social-auto-upload 目录：{vendor}。"
                "请检查 SAU_VENDOR_PATH；Docker 需挂载 ../vendor/social-auto-upload。"
            )
        try:
            from uploader.xiaohongshu_uploader.main import (  # type: ignore
                XiaoHongShuNote,
                XiaoHongShuVideo,
                cookie_auth,
                xiaohongshu_cookie_gen,
            )

            return cookie_auth, xiaohongshu_cookie_gen, XiaoHongShuNote, XiaoHongShuVideo
        except ImportError as exc:
            raise RuntimeError(format_vendor_import_error(exc, vendor)) from exc

    async def _log_step(self, context: PublishContext, step: str, status: str, message: str) -> None:
        if context.log_callback:
            await context.log_callback(step, status, message)

    async def login(self, account_id: int, account_name: str, cookie_file: str, qrcode_callback=None) -> LoginResult:
        cookie_auth, xiaohongshu_cookie_gen, _, _ = self._import_vendor()
        path = Path(cookie_file)
        path.parent.mkdir(parents=True, exist_ok=True)

        max_checks = max(1, self.settings.login_timeout_seconds // 3)
        result = await xiaohongshu_cookie_gen(
            str(path),
            poll_interval=3,
            max_checks=max_checks,
            headless=self.settings.playwright_headless,
            qrcode_callback=qrcode_callback,
        )
        qrcode = result.get("qrcode") or {}
        return LoginResult(
            success=bool(result.get("success")),
            status=str(result.get("status", "failed")),
            message=str(result.get("message", "")),
            qrcode_path=qrcode.get("image_path"),
            qrcode_data_url=qrcode.get("image_data_url"),
        )

    async def check_cookie_valid(self, cookie_file: str) -> bool:
        if not Path(cookie_file).exists():
            return False
        cookie_auth, _, _, _ = self._import_vendor()
        return await cookie_auth(cookie_file)

    async def publish(self, context: PublishContext) -> PublishResult:
        _, _, XiaoHongShuNote, XiaoHongShuVideo = self._import_vendor()

        try:
            await self._log_step(context, "validate", "running", "校验 Cookie 与素材")
            if not await self.check_cookie_valid(context.cookie_file):
                await self._log_step(context, "validate", "failed", "Cookie 无效")
                return PublishResult(success=False, message="Cookie 无效，请重新登录")

            if context.content_type == "video":
                if not context.material_paths:
                    return PublishResult(success=False, message="视频发布需要素材文件")
                await self._log_step(context, "open_page", "running", "打开视频发布页")
                uploader = XiaoHongShuVideo(
                    title=context.title,
                    file_path=context.material_paths[0],
                    desc=context.content,
                    tags=context.tags,
                    publish_date=0,
                    account_file=context.cookie_file,
                    headless=self.settings.playwright_headless,
                )
                await self._log_step(context, "upload_media", "running", "上传视频")
                await uploader.xiaohongshu_upload_video()
            else:
                if not context.material_paths:
                    return PublishResult(success=False, message="图文发布需要至少一张图片")
                await self._log_step(context, "open_page", "running", "打开图文发布页")
                uploader = XiaoHongShuNote(
                    image_paths=context.material_paths,
                    note=context.content,
                    tags=context.tags,
                    publish_date=0,
                    account_file=context.cookie_file,
                    title=context.title,
                    desc=context.content,
                    headless=self.settings.playwright_headless,
                )
                await self._log_step(context, "upload_media", "running", "上传图片")
                await self._log_step(context, "fill_title", "running", "填写标题与正文")
                await self._log_step(context, "fill_tags", "running", "填写标签")
                await uploader.xiaohongshu_upload_note()

            await self._log_step(context, "submit", "success", "发布成功")
            return PublishResult(success=True, message="发布成功")
        except Exception as exc:
            logger.exception("XHS publish failed")
            await self._log_step(context, "submit", "failed", str(exc))
            return PublishResult(success=False, message=str(exc))
