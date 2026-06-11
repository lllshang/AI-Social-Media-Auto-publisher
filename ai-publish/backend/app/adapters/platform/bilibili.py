import asyncio
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

    @staticmethod
    def _has_interactive_terminal() -> bool:
        return sys.stdin.isatty() and sys.stdout.isatty()

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
        if not self._has_interactive_terminal():
            message = (
                "B站登录需要在本地交互终端执行："
                f"`sau bilibili login --account {account_name}`。"
                "若终端二维码显示不完整，请打开当前目录下的 qrcode.png 扫码。"
                "完成后可在管理页点击「校验 Cookie」或导入 Cookie 文件。"
            )
            return LoginResult(success=False, status="manual", message=message)

        run_biliup_command = self._import_runtime()
        result = await asyncio.to_thread(
            run_biliup_command,
            ["-u", str(path), "login"],
            True,
        )
        success = result.returncode == 0 and path.exists()
        message = "B站登录成功" if success else "B站登录失败，请在本地终端重试"
        return LoginResult(success=success, status="success" if success else "failed", message=message)

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
                return PublishResult(success=False, message="Cookie 无效，请重新登录")

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
