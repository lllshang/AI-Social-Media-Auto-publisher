from __future__ import annotations

import base64
import fcntl
import hashlib
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
from urllib.parse import urlencode

from uploader.bilibili_uploader.runtime import build_biliup_runtime_path, ensure_biliup_binary

AUTH_URL_PATTERN = re.compile(
    r"https://passport\.bilibili\.com[^\s\]'\"<>]+auth_code=[^\s\]'\"<>]+",
    re.IGNORECASE,
)
MENU_READY_MARKERS = ("选择一种登录方式", "短信登录", "扫码登录", "浏览器登录")
SMS_FLOW_MARKERS = ("手机国家代码", "请输入手机号", "请输入SESSDATA")
# biliupR v1.2 默认光标在「短信登录」(index=1)。禁止发送裸 Enter 或数字键，否则会进入短信流程。
# index: 0 账号密码 | 1 短信 | 2 扫码 | 3 浏览器 | 4/5 Cookie
BILIUPR_MENU_ATTEMPTS: tuple[tuple[str, str], ...] = (
    ("\x1b[B\r", "扫码登录"),
    ("\x1b[B\x1b[B\r", "浏览器登录"),
)
QR_PREPARE_TIMEOUT_PER_ATTEMPT_SECONDS = 90
SCAN_WAIT_SECONDS_DEFAULT = 300
WEB_QR_GENERATE_URL = "https://passport.bilibili.com/x/passport-login/web/qrcode/generate"
WEB_QR_POLL_URL = "https://passport.bilibili.com/x/passport-login/web/qrcode/poll"
WEB_QR_SOURCE = "main-fe-header"
WEB_QR_GO_URL = "https://www.bilibili.com/"
WEB_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
# 网页扫码轮询：86101 未扫码 | 86090 已扫未确认 | 86038 过期
WEB_QR_POLL_WAIT_CODES = {86101, 86090}
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
        return _sanitize_login_url(match.group(0))
    for line in clean.splitlines():
        line = line.strip()
        if not line.startswith(("http://", "https://")):
            continue
        url_match = re.search(r"https?://[^\s\]'\"<>]+", line)
        if not url_match:
            continue
        url = _sanitize_login_url(url_match.group(0))
        if _is_bilibili_login_url(url):
            return url
    code_match = AUTH_CODE_ONLY_RE.search(clean)
    if code_match:
        return (
            "https://passport.bilibili.com/x/passport-tv-login/h5/qrcode/auth"
            f"?auth_code={code_match.group(1)}"
        )
    return None


def _sanitize_login_url(url: str) -> str:
    return url.strip().rstrip(".,;)]}>\"'")


def _is_bilibili_login_url(url: str) -> bool:
    lowered = url.lower()
    if not lowered.startswith(("http://", "https://")):
        return False
    if "bilibili.com" not in lowered:
        return False
    if "com.bili" in lowered:
        return False
    return any(token in lowered for token in ("auth_code=", "qrcode_key=", "passport", "/scan"))


def _parse_poll_code(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _resolve_web_scan_url(raw_url: str, qrcode_key: str) -> str:
    """优先使用 B 站 API 返回的 url（勿额外加 source，否则手机确认后服务端 poll 可能收不到成功）。"""
    url = (raw_url or "").strip()
    if url:
        if f"qrcode_key={qrcode_key}" in url:
            return url
        if "qrcode_key=" in url:
            return re.sub(r"qrcode_key=[^&]*", f"qrcode_key={qrcode_key}", url, count=1)
    params = {"navhide": "1", "qrcode_key": qrcode_key, "from": ""}
    return f"https://passport.bilibili.com/h5-app/passport/login/scan?{urlencode(params)}"


def _build_web_scan_url(qrcode_key: str) -> str:
    params = {"navhide": "1", "qrcode_key": qrcode_key, "from": ""}
    return f"https://passport.bilibili.com/h5-app/passport/login/scan?{urlencode(params)}"


def _write_biliup_cookie_file(account_path: Path, session, poll_data: dict | None = None) -> None:
    cookies = []
    for cookie in session.cookies:
        cookies.append(
            {
                "name": cookie.name,
                "value": cookie.value,
                "domain": cookie.domain or ".bilibili.com",
                "path": cookie.path or "/",
            }
        )
    if not any(item["name"] == "SESSDATA" for item in cookies):
        raise RuntimeError("登录成功但未获取 SESSDATA，请重试")
    poll_data = poll_data or {}
    payload = {
        "cookie_info": {"cookies": cookies},
        "sso": [],
        "token_info": {
            "mid": int(poll_data.get("mid") or 0),
            "access_token": str(poll_data.get("access_token") or ""),
            "refresh_token": str(poll_data.get("refresh_token") or ""),
            "expires_in": int(poll_data.get("expires_in") or 0),
        },
    }
    account_path.parent.mkdir(parents=True, exist_ok=True)
    account_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _upgrade_web_cookie_for_biliup_tv(account_path)


BILITV_APP_KEY = "4409e2ce8ffd12b8"
BILITV_APPSEC = "59b43e04ad6965f34319062b478f83dd"
BILITV_UA = (
    "Mozilla/5.0 (X11; Linux x86_64; rv:38.0) Gecko/20100101 Firefox/38.0 "
    "Iceweasel/38.2.1 BiliApp"
)


def _bilitv_sign(payload: dict) -> str:
    encoded = urlencode([(key, payload[key]) for key in payload if key != "sign"])
    return hashlib.md5((encoded + BILITV_APPSEC).encode("utf-8")).hexdigest()


def _cookie_map_from_file(cookie_path: Path) -> dict[str, str]:
    raw = cookie_path.read_text(encoding="utf-8").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    cookies = data.get("cookie_info", {}).get("cookies", [])
    result: dict[str, str] = {}
    if isinstance(cookies, list):
        for item in cookies:
            if isinstance(item, dict):
                name = str(item.get("name") or "").strip()
                value = str(item.get("value") or "").strip()
                if name and value:
                    result[name] = value
    return result


def _is_biliup_upload_ready(cookie_path: Path) -> bool:
    try:
        data = json.loads(cookie_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    if "sso" not in data:
        return False
    token_info = data.get("token_info") if isinstance(data.get("token_info"), dict) else {}
    return bool(str(token_info.get("access_token") or "").strip())


def _upgrade_web_cookie_for_biliup_tv(cookie_path: Path) -> bool:
    """将网页扫码 Cookie 转为 biliup-cli 可识别的 TV token 格式（含 sso）。"""
    if _is_biliup_upload_ready(cookie_path):
        return True
    import requests

    cookie_map = _cookie_map_from_file(cookie_path)
    sessdata = cookie_map.get("SESSDATA", "")
    bili_jct = cookie_map.get("bili_jct", "")
    if not sessdata or not bili_jct:
        logger.warning("bilibili cookie upgrade skipped: missing SESSDATA or bili_jct")
        return False

    session = requests.Session()
    session.headers.update({"User-Agent": BILITV_UA})

    ts = int(time.time())
    auth_payload = {"appkey": BILITV_APP_KEY, "local_id": "0", "ts": ts, "sign": ""}
    auth_payload["sign"] = _bilitv_sign(auth_payload)
    try:
        auth_resp = session.post(
            "https://passport.bilibili.com/x/passport-tv-login/qrcode/auth_code",
            data=auth_payload,
            timeout=(5, 30),
        )
        auth_resp.raise_for_status()
        auth_data = auth_resp.json()
    except Exception as exc:
        logger.warning("bilibili tv auth_code failed: %s", exc)
        return False

    auth_code = ""
    if isinstance(auth_data, dict):
        inner = auth_data.get("data")
        if isinstance(inner, dict):
            auth_code = str(inner.get("auth_code") or "").strip()
    if not auth_code:
        logger.warning("bilibili tv auth_code missing: %s", auth_data)
        return False

    confirm_payload = {
        "auth_code": auth_code,
        "csrf": bili_jct,
        "scanning_type": 3,
    }
    cookie_header = f"SESSDATA={sessdata}; bili_jct={bili_jct}"
    try:
        confirm_resp = session.post(
            "https://passport.bilibili.com/x/passport-tv-login/h5/qrcode/confirm",
            headers={"Cookie": cookie_header, "User-Agent": BILITV_UA},
            data=confirm_payload,
            timeout=(5, 30),
        )
        confirm_resp.raise_for_status()
        confirm_data = confirm_resp.json()
        if isinstance(confirm_data, dict) and confirm_data.get("code") not in (0, None):
            logger.warning("bilibili tv confirm rejected: %s", confirm_data)
            return False
    except Exception as exc:
        logger.warning("bilibili tv confirm failed: %s", exc)
        return False

    for _ in range(30):
        ts = int(time.time())
        poll_payload = {
            "appkey": BILITV_APP_KEY,
            "auth_code": auth_code,
            "local_id": "0",
            "ts": ts,
            "sign": "",
        }
        poll_payload["sign"] = _bilitv_sign(poll_payload)
        try:
            poll_resp = session.post(
                "https://passport.bilibili.com/x/passport-tv-login/qrcode/poll",
                data=poll_payload,
                timeout=(5, 30),
            )
            poll_resp.raise_for_status()
            poll_data = poll_resp.json()
        except Exception as exc:
            logger.warning("bilibili tv poll failed: %s", exc)
            time.sleep(1)
            continue

        if not isinstance(poll_data, dict):
            time.sleep(1)
            continue
        if poll_data.get("code") == 86039:
            logger.warning("bilibili tv poll timeout")
            return False
        if poll_data.get("code") != 0:
            time.sleep(1)
            continue

        login_info = poll_data.get("data")
        if not isinstance(login_info, dict):
            logger.warning("bilibili tv poll missing login data: %s", poll_data)
            return False
        if "sso" not in login_info:
            login_info["sso"] = []
        login_info["platform"] = "BiliTV"
        cookie_path.write_text(json.dumps(login_info, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.warning("bilibili cookie upgraded to TV token for biliup upload")
        return True

    logger.warning("bilibili tv poll exhausted without success")
    return False


def prepare_biliup_cookie_file(cookie_file: str) -> str:
    """上传前规范化 Cookie 文件，补齐 biliup-cli 要求的 sso / TV token。"""
    cookie_path = Path(cookie_file).expanduser().resolve()
    if not cookie_path.exists():
        return cookie_file
    try:
        data = json.loads(cookie_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return cookie_file
    if not isinstance(data, dict):
        return cookie_file
    changed = False
    if "sso" not in data:
        data["sso"] = []
        changed = True
    if changed and not _is_biliup_upload_ready(cookie_path):
        cookie_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    if not _is_biliup_upload_ready(cookie_path):
        _upgrade_web_cookie_for_biliup_tv(cookie_path)
    return str(cookie_path)


def _cookie_header_from_file(cookie_path: Path) -> str:
    raw = cookie_path.read_text(encoding="utf-8").strip()
    if not raw:
        return ""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return raw if "SESSDATA" in raw else ""
    cookies = data.get("cookie_info", {}).get("cookies", [])
    if isinstance(cookies, list) and cookies:
        parts = []
        for item in cookies:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            value = str(item.get("value") or "").strip()
            if name and value:
                parts.append(f"{name}={value}")
        return "; ".join(parts)
    return ""


def validate_bilibili_cookie_file(cookie_file: str) -> bool:
    """网页扫码 Cookie 用 nav 接口校验；biliup renew 仅适用于 TV/App token 登录。"""
    import requests

    cookie_path = Path(cookie_file).expanduser()
    if not cookie_path.exists() or cookie_path.stat().st_size < 8:
        return False
    cookie_header = _cookie_header_from_file(cookie_path)
    if "SESSDATA" not in cookie_header:
        return False
    try:
        response = requests.get(
            "https://api.bilibili.com/x/web-interface/nav",
            headers={
                "User-Agent": WEB_USER_AGENT,
                "Cookie": cookie_header,
                "Referer": "https://www.bilibili.com/",
            },
            timeout=(5, 15),
        )
        payload = response.json()
    except Exception as exc:
        logger.warning("bilibili nav cookie validate failed: %s", exc)
        return False
    data = payload.get("data") if isinstance(payload, dict) else None
    return payload.get("code") == 0 and isinstance(data, dict) and bool(data.get("isLogin"))


def _run_bilibili_web_qrcode_login(
    account_file: str,
    qrcode_callback=None,
    progress_callback=None,
    timeout_seconds: int = 300,
) -> BilibiliLoginOutcome:
    import requests

    account_path = Path(account_file).expanduser().resolve()
    account_path.parent.mkdir(parents=True, exist_ok=True)
    scan_wait_seconds = max(120, int(timeout_seconds or SCAN_WAIT_SECONDS_DEFAULT))
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": WEB_USER_AGENT,
            "Referer": "https://www.bilibili.com/",
            "Origin": "https://www.bilibili.com",
            "Accept": "application/json, text/plain, */*",
        }
    )

    try:
        session.get(WEB_QR_GO_URL, timeout=(5, 15))
    except Exception as exc:
        logger.warning("bilibili warmup www failed: %s", exc)

    _emit_progress(progress_callback, "正在获取 B 站网页扫码…")
    try:
        response = session.get(
            WEB_QR_GENERATE_URL,
            params={"source": WEB_QR_SOURCE, "go_url": WEB_QR_GO_URL},
            timeout=(5, 30),
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        logger.warning("bilibili web qrcode generate failed: %s", exc)
        return BilibiliLoginOutcome(False, "failed", "暂时无法获取 B 站扫码，将尝试备用方式")

    if payload.get("code") != 0:
        return BilibiliLoginOutcome(False, "failed", "暂时无法获取 B 站扫码，将尝试备用方式")

    data = payload.get("data") or {}
    qrcode_key = str(data.get("qrcode_key") or "").strip()
    raw_scan_url = str(data.get("url") or "").strip()
    if not qrcode_key:
        return BilibiliLoginOutcome(False, "failed", "B 站扫码数据无效，将尝试备用方式")

    scan_url = _resolve_web_scan_url(raw_scan_url, qrcode_key)
    logger.warning("bilibili web qrcode ready key=%s… url=%s", qrcode_key[:8], scan_url[:80])

    image_path = account_path.with_name(f"{account_path.stem}_login_qrcode.png")
    data_url = _make_qrcode_data_url(scan_url)
    _save_qrcode_png(scan_url, image_path)
    if qrcode_callback:
        qrcode_callback({"image_data_url": data_url, "image_path": str(image_path)})
    _emit_progress(
        progress_callback,
        "请使用哔哩哔哩 App 首页「扫一扫」扫码（勿用云视听/TV 登录）",
        "waiting_scan",
    )

    deadline = time.time() + scan_wait_seconds
    last_status: int | None = None
    poll_interval = 2.0
    while time.time() < deadline:
        try:
            poll_response = session.get(
                WEB_QR_POLL_URL,
                params={"qrcode_key": qrcode_key, "source": WEB_QR_SOURCE},
                timeout=(5, 30),
            )
            poll_response.raise_for_status()
            poll_payload = poll_response.json()
        except Exception as exc:
            logger.warning("bilibili web qrcode poll failed: %s", exc)
            time.sleep(poll_interval)
            continue

        if _parse_poll_code(poll_payload.get("code")) not in (None, 0):
            logger.warning("bilibili web qrcode poll top-level error: %s", poll_payload)
            time.sleep(poll_interval)
            continue

        poll_data = poll_payload.get("data")
        if not isinstance(poll_data, dict):
            logger.warning("bilibili web qrcode poll missing data: %s", poll_payload)
            time.sleep(poll_interval)
            continue

        poll_code = _parse_poll_code(poll_data.get("code"))
        if poll_code is None:
            logger.warning("bilibili web qrcode poll invalid code: %s", poll_payload)
            time.sleep(poll_interval)
            continue

        poll_message = str(poll_data.get("message") or "")
        if poll_code != last_status:
            last_status = poll_code
            logger.warning("bilibili web poll status=%s key=%s…", poll_code, qrcode_key[:8])
            if poll_code == 86090:
                _emit_progress(progress_callback, "已扫码，请在手机上点击确认登录…", "waiting_scan")
                poll_interval = 0.8
            elif poll_code == 86101:
                _emit_progress(progress_callback, "等待扫码…", "waiting_scan")
                poll_interval = 2.0

        if poll_code == 0:
            refresh_url = str(poll_data.get("url") or "").strip()
            if refresh_url:
                try:
                    session.get(refresh_url, timeout=(5, 30), allow_redirects=True)
                except Exception as exc:
                    logger.warning("bilibili web login refresh url failed: %s", exc)
            try:
                _write_biliup_cookie_file(account_path, session, poll_data)
            except Exception as exc:
                logger.warning("bilibili web login cookie write failed: %s", exc)
                return BilibiliLoginOutcome(
                    False,
                    "failed",
                    f"扫码成功但保存 Cookie 失败：{exc}",
                    qrcode_data_url=data_url,
                    qrcode_path=str(image_path),
                )
            logger.warning("bilibili web login success account=%s", account_path.name)
            if not validate_bilibili_cookie_file(str(account_path)):
                logger.warning("bilibili web login cookie nav validate failed account=%s", account_path.name)
                return BilibiliLoginOutcome(
                    False,
                    "failed",
                    "扫码成功但 Cookie 校验未通过，请重试",
                    qrcode_data_url=data_url,
                    qrcode_path=str(image_path),
                )
            return BilibiliLoginOutcome(
                True,
                "success",
                "B站扫码登录成功",
                qrcode_data_url=data_url,
                qrcode_path=str(image_path),
            )

        if poll_code == 86038:
            return BilibiliLoginOutcome(
                False,
                "timeout",
                "二维码已过期，请关闭窗口后重新扫码",
                qrcode_data_url=data_url,
                qrcode_path=str(image_path),
            )

        if poll_code not in WEB_QR_POLL_WAIT_CODES:
            return BilibiliLoginOutcome(
                False,
                "failed",
                poll_message or "扫码登录失败，请重试",
                qrcode_data_url=data_url,
                qrcode_path=str(image_path),
            )

        time.sleep(poll_interval)

    logger.warning("bilibili web poll timeout key=%s… last=%s", qrcode_key[:8], last_status)

    return BilibiliLoginOutcome(
        False,
        "timeout",
        _user_message("timeout", qrcode_sent=True),
        qrcode_data_url=data_url,
        qrcode_path=str(image_path),
    )


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
        binary_path = ensure_biliup_binary(
            force_check=False,
            progress_callback=lambda msg: _emit_progress(progress_callback, msg, "starting"),
        )
    except Exception as exc:
        return BilibiliLoginOutcome(False, "failed", _user_message(str(exc)))

    scan_wait_seconds = max(120, int(timeout_seconds or SCAN_WAIT_SECONDS_DEFAULT))
    last_failure: BilibiliLoginOutcome | None = None
    for menu_keys, menu_label in BILIUPR_MENU_ATTEMPTS:
        _emit_progress(progress_callback, f"正在启动 B 站{menu_label}…")
        outcome = _attempt_biliup_login_pty(
            binary_path=binary_path,
            account_path=account_path,
            work_dir=work_dir,
            menu_keys=menu_keys,
            menu_label=menu_label,
            qrcode_callback=qrcode_callback,
            progress_callback=progress_callback,
            scan_wait_seconds=scan_wait_seconds,
            proxy_url=proxy_url,
        )
        if outcome.success or outcome.qrcode_data_url:
            return outcome
        last_failure = outcome
        logger.warning(
            "biliup login attempt failed via %s: status=%s message=%s",
            menu_label,
            outcome.status,
            outcome.message,
        )
    return last_failure or BilibiliLoginOutcome(False, "failed", "B站登录失败，请稍后重试")


def _attempt_biliup_login_pty(
    *,
    binary_path: Path,
    account_path: Path,
    work_dir: Path,
    menu_keys: str,
    menu_label: str,
    qrcode_callback=None,
    progress_callback=None,
    scan_wait_seconds: int,
    proxy_url: str | None,
) -> BilibiliLoginOutcome:
    logger.info(
        "biliup login attempt: binary=%s account=%s mode=%s",
        binary_path,
        account_path,
        menu_label,
    )

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
    menu_sent = False
    wrong_flow = False
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
            if not qrcode_sent and now - started_at > QR_PREPARE_TIMEOUT_PER_ATTEMPT_SECONDS:
                logger.warning(
                    "biliup login prepare timeout after %ss (mode=%s)",
                    QR_PREPARE_TIMEOUT_PER_ATTEMPT_SECONDS,
                    menu_label,
                )
                break
            if qrcode_sent and now - qrcode_shown_at > scan_wait_seconds:
                logger.warning("biliup login scan wait timeout after %ss", scan_wait_seconds)
                break
            if process.poll() is not None:
                break

            chunk = _read_pty(master_fd)
            if chunk:
                output += chunk

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

            clean_output = _strip_ansi(output)
            if not qrcode_sent and menu_sent and any(marker in clean_output for marker in SMS_FLOW_MARKERS):
                logger.warning("biliup entered SMS/password flow while expecting %s", menu_label)
                wrong_flow = True
                break

            if not qrcode_sent and not menu_sent and any(marker in clean_output for marker in MENU_READY_MARKERS):
                time.sleep(0.6)
                _write_pty(master_fd, menu_keys)
                menu_sent = True
                _emit_progress(progress_callback, f"已选择{menu_label}，等待二维码…")
                output = ""

            if not chunk:
                time.sleep(0.15)

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
                logger.warning("biliup login ended without qrcode, mode=%s tail=%s", menu_label, detail)
                if wrong_flow:
                    message = f"未能进入{menu_label}，将尝试其他登录方式"
                else:
                    message = f"未能获取登录二维码（{menu_label}），请重试或查看 API 日志"
                return BilibiliLoginOutcome(
                    False,
                    "failed",
                    message,
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
            message = f"未能获取登录二维码（{menu_label}），请稍后重试"
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

    web_outcome = await loop.run_in_executor(
        None,
        lambda: _run_bilibili_web_qrcode_login(
            account_file,
            qrcode_callback=qrcode_callback,
            progress_callback=progress_callback,
            timeout_seconds=timeout_seconds,
        ),
    )
    if web_outcome.success or web_outcome.qrcode_data_url:
        return web_outcome

    logger.info("bilibili web qrcode login unavailable, fallback to biliup PTY: %s", web_outcome.message)
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
