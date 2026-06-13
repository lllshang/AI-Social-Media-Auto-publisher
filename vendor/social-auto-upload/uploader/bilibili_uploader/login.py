from __future__ import annotations

import base64
import fcntl
import io
import json
import logging
import os
import pty
import re
import select
import struct
import subprocess
import termios
import time
from typing import Callable
from dataclasses import dataclass
from pathlib import Path

from uploader.bilibili_uploader.runtime import build_biliup_runtime_path, ensure_biliup_binary

AUTH_URL_PATTERN = re.compile(
    r"https://passport\.bilibili\.com[^\s\]'\"<>]+auth_code=[^\s\]'\"<>]+",
    re.IGNORECASE,
)
MENU_MARKERS = ("请选择", "登录方式", "短信登录", "浏览器登录", "扫码登录", "登录", "哔哩哔哩")
MENU_KEY_SEQUENCES = ("1\r", "3\r", "2\r", "\x1b[B\x1b[B\r", "\x1b[B\r", "\r")
QR_PREPARE_TIMEOUT_SECONDS = 240
SCAN_WAIT_SECONDS_DEFAULT = 300
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
AUTH_CODE_ONLY_RE = re.compile(r"auth_code=([A-Za-z0-9._-]+)", re.IGNORECASE)
logger = logging.getLogger(__name__)


@dataclass
class BilibiliLoginOutcome:
    success: bool
    status: str
    message: str
    qrcode_data_url: str = ""
    qrcode_path: str = ""


def _user_message(raw: str, *, qrcode_sent: bool = False) -> str:
    lowered = raw.lower()
    if "not a terminal" in lowered:
        return "服务器登录环境未就绪，请联系管理员检查部署配置"
    if "timeout" in lowered or "超时" in raw:
        if qrcode_sent:
            return "扫码后等待登录结果超时，请关闭窗口后重新点击「扫码登录」"
        return "准备登录超时（首次可能需下载 biliup 组件 1–3 分钟），请重试"
    if "github" in lowered or "release" in lowered:
        return "暂时无法连接登录组件，请稍后重试或联系管理员"
    if "auth_code" in lowered or "qrcode" in lowered or "二维码" in raw:
        return "未能获取登录二维码，请稍后重试"
    return "B站登录失败，请稍后重试"


def _render_qrcode_png_bytes(url: str) -> bytes:
    import segno

    buffer = io.BytesIO()
    segno.make(url, error="L", boost_error=False).save(buffer, kind="png", scale=6, border=2)
    return buffer.getvalue()


def _save_qrcode_png(url: str, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(_render_qrcode_png_bytes(url))
    return output_path


def _make_qrcode_data_url(url: str) -> str:
    encoded = base64.b64encode(_render_qrcode_png_bytes(url)).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _read_pty(master_fd: int, timeout: float = 0.25) -> str:
    readable, _, _ = select.select([master_fd], [], [], timeout)
    if not readable:
        return ""
    try:
        chunk = os.read(master_fd, 4096)
    except OSError:
        return ""
    return chunk.decode("utf-8", errors="replace")


def _write_pty(master_fd: int, payload: str) -> None:
    os.write(master_fd, payload.encode("utf-8"))


def _strip_ansi(text: str) -> str:
    return ANSI_ESCAPE_RE.sub("", text)


def _extract_auth_url(text: str) -> str | None:
    clean = _strip_ansi(text)
    match = AUTH_URL_PATTERN.search(clean)
    if match:
        return match.group(0)
    code_match = AUTH_CODE_ONLY_RE.search(clean)
    if code_match:
        return f"https://passport.bilibili.com/h5-app/passport/login/auth?auth_code={code_match.group(1)}"
    return None


def _set_pty_window_size(fd: int, rows: int = 30, cols: int = 100) -> None:
    try:
        size = struct.pack("HHHH", rows, cols, 0, 0)
        fcntl.ioctl(fd, termios.TIOCSWINSZ, size)
    except OSError:
        pass


def _emit_progress(progress_callback: Callable[[str, str], None] | None, message: str, status: str = "starting") -> None:
    if progress_callback:
        progress_callback(message, status)


def _cookie_ready(account_file: Path) -> bool:
    if not account_file.exists() or account_file.stat().st_size < 8:
        return False
    try:
        json.loads(account_file.read_text(encoding="utf-8"))
        return True
    except (json.JSONDecodeError, OSError):
        return account_file.stat().st_size > 32


def _load_qrcode_png_as_data_url(qrcode_path: Path) -> str:
    encoded = base64.b64encode(qrcode_path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _run_biliup_login_pty(
    account_file: str,
    qrcode_callback=None,
    progress_callback=None,
    timeout_seconds: int = 300,
    proxy_url: str | None = None,
) -> BilibiliLoginOutcome:
    account_path = Path(account_file).expanduser().resolve()
    account_path.parent.mkdir(parents=True, exist_ok=True)
    work_dir = account_path.parent

    _emit_progress(progress_callback, "正在检查 B 站登录组件…")
    try:
        binary_path = ensure_biliup_binary(force_check=False)
    except Exception as exc:
        return BilibiliLoginOutcome(False, "failed", _user_message(str(exc)))

    scan_wait_seconds = max(120, int(timeout_seconds or SCAN_WAIT_SECONDS_DEFAULT))
    _emit_progress(progress_callback, "正在启动 B 站登录，首次可能需 1–3 分钟准备组件…")

    master_fd, slave_fd = pty.openpty()
    _set_pty_window_size(master_fd)
    _set_pty_window_size(slave_fd)
    command = [str(binary_path)]
    if proxy_url:
        command.extend(["-p", proxy_url])
    command.extend(["-u", str(account_path), "login"])
    child_env = os.environ.copy()
    child_env.setdefault("TERM", "xterm-256color")
    child_env.setdefault("LANG", "C.UTF-8")
    process = subprocess.Popen(
        command,
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        cwd=str(work_dir),
        close_fds=True,
        env=child_env,
    )
    os.close(slave_fd)

    output = ""
    menu_attempt = 0
    last_menu_try_at = 0.0
    qrcode_sent = False
    qrcode_shown_at = 0.0
    last_auth_url = ""
    last_qrcode_path = ""
    qrcode_path = work_dir / "qrcode.png"
    qrcode_mtime_before = qrcode_path.stat().st_mtime if qrcode_path.exists() else 0.0
    started_at = time.time()

    try:
        while True:
            now = time.time()
            if not qrcode_sent and now - started_at > QR_PREPARE_TIMEOUT_SECONDS:
                logger.warning("biliup login prepare timeout after %ss", QR_PREPARE_TIMEOUT_SECONDS)
                break
            if qrcode_sent and now - qrcode_shown_at > scan_wait_seconds:
                logger.warning("biliup login scan wait timeout after %ss", scan_wait_seconds)
                break
            if process.poll() is not None:
                break

            chunk = _read_pty(master_fd)
            if chunk:
                output += chunk

            clean_output = _strip_ansi(output)
            if not qrcode_sent and any(marker in clean_output for marker in MENU_MARKERS):
                if menu_attempt == 0 or now - last_menu_try_at >= 8:
                    if menu_attempt < len(MENU_KEY_SEQUENCES):
                        time.sleep(0.4)
                        _write_pty(master_fd, MENU_KEY_SEQUENCES[menu_attempt])
                        menu_attempt += 1
                        last_menu_try_at = now
                        _emit_progress(
                            progress_callback,
                            f"正在选择扫码登录方式（{menu_attempt}/{len(MENU_KEY_SEQUENCES)}）…",
                        )
                        output = ""

            auth_url = _extract_auth_url(output)
            if auth_url and (not qrcode_sent or auth_url != last_auth_url):
                _emit_progress(progress_callback, "正在生成二维码…")
                image_path = account_path.with_name(f"{account_path.stem}_login_qrcode.png")
                data_url = _make_qrcode_data_url(auth_url)
                _save_qrcode_png(auth_url, image_path)
                payload = {"image_data_url": data_url, "image_path": str(image_path)}
                last_qrcode_path = str(image_path)
                last_auth_url = auth_url
                if qrcode_callback:
                    qrcode_callback(payload)
                qrcode_sent = True
                qrcode_shown_at = time.time()
                _emit_progress(progress_callback, "请使用哔哩哔哩 App 扫码（二维码约 60 秒内有效）", "waiting_scan")

            if not qrcode_sent and qrcode_path.exists():
                current_mtime = qrcode_path.stat().st_mtime
                if current_mtime > qrcode_mtime_before:
                    data_url = _load_qrcode_png_as_data_url(qrcode_path)
                    image_path = account_path.with_name(f"{account_path.stem}_login_qrcode.png")
                    image_path.write_bytes(qrcode_path.read_bytes())
                    payload = {"image_data_url": data_url, "image_path": str(image_path)}
                    last_qrcode_path = str(image_path)
                    if qrcode_callback:
                        qrcode_callback(payload)
                    qrcode_sent = True
                    qrcode_shown_at = time.time()
                    _emit_progress(progress_callback, "请使用哔哩哔哩 App 扫码", "waiting_scan")

            if not chunk:
                time.sleep(0.15)

        # 给 biliup 一点时间落盘 cookie
        for _ in range(20):
            if process.poll() is not None:
                break
            if _cookie_ready(account_path):
                break
            time.sleep(0.25)

        return_code = process.poll()
        detail = _strip_ansi((output or "").strip())[-600:]
        if return_code is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
            if not qrcode_sent:
                logger.warning("biliup login ended without qrcode, tail=%s", detail)
                return BilibiliLoginOutcome(
                    False,
                    "failed",
                    "未能获取登录二维码（首次登录需下载 biliup，约 1–3 分钟）；请重试或查看 API 日志",
                    qrcode_data_url="",
                    qrcode_path="",
                )
            return BilibiliLoginOutcome(
                False,
                "timeout",
                _user_message("timeout", qrcode_sent=True),
                qrcode_data_url=_last_qrcode_data_url(work_dir, account_path, last_qrcode_path),
                qrcode_path=last_qrcode_path,
            )

        if return_code == 0 and _cookie_ready(account_path):
            return BilibiliLoginOutcome(
                True,
                "success",
                "B站扫码登录成功",
                qrcode_data_url=_last_qrcode_data_url(work_dir, account_path, last_qrcode_path),
                qrcode_path=last_qrcode_path,
            )

        message = _user_message(detail or f"exit {return_code}", qrcode_sent=qrcode_sent)
        if not qrcode_sent and "github" not in detail.lower():
            message = "未能获取登录二维码，请稍后重试；若持续失败请联系管理员检查服务器网络"
        return BilibiliLoginOutcome(
            False,
            "failed",
            message,
            qrcode_data_url=_last_qrcode_data_url(work_dir, account_path, last_qrcode_path),
            qrcode_path=last_qrcode_path,
        )
    finally:
        try:
            os.close(master_fd)
        except OSError:
            pass
        if process.poll() is None:
            try:
                process.kill()
            except OSError:
                pass


def _last_qrcode_data_url(work_dir: Path, account_path: Path, preferred_path: str = "") -> str:
    if preferred_path and Path(preferred_path).exists():
        return _load_qrcode_png_as_data_url(Path(preferred_path))
    generated = account_path.with_name(f"{account_path.stem}_login_qrcode.png")
    if generated.exists():
        return _load_qrcode_png_as_data_url(generated)
    fallback = work_dir / "qrcode.png"
    if fallback.exists():
        return _load_qrcode_png_as_data_url(fallback)
    return ""


async def bilibili_cookie_gen(
    account_file: str,
    qrcode_callback=None,
    progress_callback=None,
    timeout_seconds: int = 300,
    proxy_url: str | None = None,
) -> BilibiliLoginOutcome:
    import asyncio

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        lambda: _run_biliup_login_pty(
            account_file,
            qrcode_callback=qrcode_callback,
            progress_callback=progress_callback,
            timeout_seconds=timeout_seconds,
            proxy_url=proxy_url,
        ),
    )
