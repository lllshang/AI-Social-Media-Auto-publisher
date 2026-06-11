import asyncio
import inspect
import sys
from pathlib import Path

from loguru import logger

from app.adapters.base import LoginResult, PublishContext, PublishResult
from app.config import get_settings
from app.utils.runtime_env import format_vendor_import_error


class BilibiliPlatformAdapter:
    platform = "bilibili"

    def __init__(self) -> None:
        self.settings = get_settings()
        self._ensure_vendor_path()

    def _ensure_vendor_path(self) -> None:
        vendor = Path(self.settings.sau_vendor_path).resolve()
        if vendor.exists() and str(vendor) not in sys.path:
            sys.path.insert(0, str(vendor))

    def _import_runtime(self):
        self._ensure_vendor_path()
        vendor = Path(self.settings.sau_vendor_path).resolve()
        if not vendor.exists():
            raise RuntimeError(
                f"未找到 social-auto-upload 目录：{vendor}。"
                "请检查 SAU_VENDOR_PATH；Docker 需挂载 ../vendor/social-auto-upload。"
            )
        try:
            from uploader.bilibili_uploader.runtime import run_biliup_command  # type: ignore

            return run_biliup_command
        except ImportError as exc:
            raise RuntimeError(format_vendor_import_error(exc, vendor)) from exc

    def _import_login(self):
        self._ensure_vendor_path()
        vendor = Path(self.settings.sau_vendor_path).resolve()
        try:
            from uploader.bilibili_uploader.login import bilibili_cookie_gen  # type: ignore

            return bilibili_cookie_gen
        except ImportError as exc:
            raise RuntimeError(format_vendor_import_error(exc, vendor)) from exc

    def _wrap_qrcode_callback(self, qrcode_callback):
        if not qrcode_callback:
            return None

        loop = asyncio.get_running_loop()

        def _sync_emit(payload: dict) -> None:
            result = qrcode_callback(payload)
            if inspect.isawaitable(result):
                future = asyncio.run_coroutine_threadsafe(result, loop)
                future.result(timeout=10)

        return _sync_emit

    async def _log_step(self, context: PublishContext, step: str, status: str, message: str) -> None:
        if context.log_callback:
            await context.log_callback(step, status, message)

    async def login(
        self,
        account_id: int,
        account_name: str,
        cookie_file: str,
        qrcode_callback=None,
    ) -> LoginResult:
        path = Path(cookie_file)
        path.parent.mkdir(parents=True, exist_ok=True)

        bilibili_cookie_gen = self._import_login()
        from app.utils.login_poll import login_poll_params

        _, max_checks = login_poll_params(self.settings)
        timeout_seconds = max(self.settings.login_timeout_seconds, max_checks)

        outcome = await bilibili_cookie_gen(
            str(path),
            qrcode_callback=self._wrap_qrcode_callback(qrcode_callback),
            timeout_seconds=timeout_seconds,
        )
        return LoginResult(
            success=outcome.success,
            status=outcome.status,
            message=outcome.message,
            qrcode_path=outcome.qrcode_path or None,
            qrcode_data_url=outcome.qrcode_data_url or None,
        )

    async def check_cookie_valid(self, cookie_file: str) -> bool:
        if not Path(cookie_file).exists():
            return False
        run_biliup_command = self._import_runtime()
        result = await asyncio.to_thread(
            run_biliup_command,
            ["-u", cookie_file, "renew"],
        )
        return result.returncode == 0

    async def publish(self, context: PublishContext) -> PublishResult:
        if context.content_type != "video":
            return PublishResult(success=False, message="B站仅支持视频发布")

        tid = context.bilibili_tid
        if not tid:
            return PublishResult(success=False, message="请设置 B站分区 tid")

        if not context.material_paths:
            return PublishResult(success=False, message="视频发布需要素材文件")

        video_path = Path(context.material_paths[0])
        if not video_path.exists():
            return PublishResult(success=False, message=f"视频文件不存在: {video_path}")

        run_biliup_command = self._import_runtime()

        try:
            await self._log_step(context, "validate", "running", "校验 Cookie 与素材")
            if not await self.check_cookie_valid(context.cookie_file):
                await self._log_step(context, "validate", "failed", "Cookie 无效")
                return PublishResult(success=False, message="账号未登录或已失效，请重新扫码登录")

            arguments = [
                "-u",
                context.cookie_file,
                "upload",
                str(video_path),
                "--title",
                context.title,
                "--desc",
                context.content or "",
                "--tid",
                str(tid),
            ]
            if context.tags:
                arguments.extend(["--tag", ",".join(context.tags)])
            if context.publish_time:
                arguments.extend(["--dtime", str(int(context.publish_time.timestamp()))])

            await self._log_step(context, "upload_media", "running", "通过 biliup 上传视频")
            result = await asyncio.to_thread(run_biliup_command, arguments)
            if result.returncode != 0:
                message = (result.stderr or result.stdout or "").strip() or "B站上传失败"
                await self._log_step(context, "submit", "failed", message)
                return PublishResult(success=False, message=message)

            await self._log_step(context, "submit", "success", "B站视频已提交上传")
            return PublishResult(success=True, message="B站视频已提交上传")
        except Exception as exc:
            logger.exception("Bilibili publish failed")
            await self._log_step(context, "submit", "failed", str(exc))
            return PublishResult(success=False, message=str(exc))
