from pathlib import Path

from loguru import logger

from app.adapters.base import LoginResult, PublishContext, PublishResult
from app.adapters.platform.xhs import XhsPlatformAdapter


class KuaishouPlatformAdapter(XhsPlatformAdapter):
    platform = "kuaishou"

    def _import_vendor(self):
        self._ensure_vendor_path()
        self._configure_vendor_conf()
        vendor = Path(self.settings.sau_vendor_path).resolve()
        if not vendor.exists():
            raise RuntimeError(
                f"未找到 social-auto-upload 目录：{vendor}。"
                "请检查 SAU_VENDOR_PATH；Docker 需挂载 ../vendor/social-auto-upload。"
            )
        from app.utils.runtime_env import format_vendor_import_error

        try:
            from uploader.ks_uploader.main import (  # type: ignore
                KSNote,
                KSVideo,
                cookie_auth,
                get_ks_cookie,
            )

            return cookie_auth, get_ks_cookie, KSNote, KSVideo
        except ImportError as exc:
            raise RuntimeError(format_vendor_import_error(exc, vendor)) from exc

    async def login(self, account_id: int, account_name: str, cookie_file: str, qrcode_callback=None) -> LoginResult:
        _, get_ks_cookie, _, _ = self._import_vendor()
        path = Path(cookie_file)
        path.parent.mkdir(parents=True, exist_ok=True)

        from app.utils.login_poll import login_poll_params

        poll_interval, max_checks = login_poll_params(self.settings)
        result = await get_ks_cookie(
            str(path),
            poll_interval=poll_interval,
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

    async def publish(self, context: PublishContext) -> PublishResult:
        _, _, KSNote, KSVideo = self._import_vendor()

        try:
            await self._log_step(context, "validate", "running", "校验 Cookie 与素材")
            if not await self.check_cookie_valid(context.cookie_file):
                await self._log_step(context, "validate", "failed", "Cookie 无效")
                return PublishResult(success=False, message="Cookie 无效，请重新登录")

            if context.content_type == "video":
                if not context.material_paths:
                    return PublishResult(success=False, message="视频发布需要素材文件")
                await self._log_step(context, "open_page", "running", "打开视频发布页")
                uploader = KSVideo(
                    title=context.title,
                    file_path=context.material_paths[0],
                    tags=context.tags,
                    desc=context.content,
                    publish_date=0,
                    account_file=context.cookie_file,
                    headless=self.settings.playwright_headless,
                )
                await self._log_step(context, "upload_media", "running", "上传视频")
                await uploader.main()
            else:
                if not context.material_paths:
                    return PublishResult(success=False, message="图文发布需要至少一张图片")
                await self._log_step(context, "open_page", "running", "打开图文发布页")
                uploader = KSNote(
                    image_paths=context.material_paths,
                    note=context.content,
                    tags=context.tags,
                    title=context.title,
                    publish_date=0,
                    account_file=context.cookie_file,
                    headless=self.settings.playwright_headless,
                )
                await self._log_step(context, "upload_media", "running", "上传图片")
                await self._log_step(context, "fill_title", "running", "填写标题与正文")
                await self._log_step(context, "fill_tags", "running", "填写标签")
                await uploader.main()

            await self._log_step(context, "submit", "success", "发布成功")
            return PublishResult(success=True, message="发布成功")
        except Exception as exc:
            logger.exception("Kuaishou publish failed")
            await self._log_step(context, "submit", "failed", str(exc))
            return PublishResult(success=False, message=str(exc))
