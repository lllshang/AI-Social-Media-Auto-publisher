from pathlib import Path

from app.config import get_settings
from app.utils.playwright_browser import chromium_available, find_chromium_executable, is_docker_runtime


def qr_login_supported() -> bool:
    """Whether server can run headless browser QR login (all platforms)."""
    if not is_docker_runtime():
        return True
    return chromium_available()


def xhs_qr_login_supported() -> bool:
    """Backward-compatible alias used by frontend."""
    return qr_login_supported()


def headless_publish_supported() -> bool:
    """Whether server can run Playwright publish without local Chrome."""
    return chromium_available()


def docker_login_hint() -> str:
    if qr_login_supported():
        return (
            "服务器将以无头 Chromium 打开登录页，二维码会显示在本页面，"
            "请使用对应平台 App 扫码完成绑定；发布任务也将在服务器无头执行。"
        )
    return (
        "服务器尚未安装 Chromium，无法网页扫码或无头发布。"
        "请执行 bash scripts/install-playwright-browser.sh 或重建 API 镜像，"
        "或在本地登录后通过 Cookie 导入。"
    )


def format_vendor_import_error(exc: ImportError, vendor_path: Path) -> str:
    root = str(exc)
    if "Read-only file system" in root or "Errno 30" in root:
        detail = "vendor 目录为只读挂载，social-auto-upload 无法写入日志"
    elif "libxcb" in root or "libGL" in root or "libgobject" in root:
        detail = "OpenCV 缺少系统库（如 libxcb），请重建 Docker API 镜像"
    elif "No module named" in root:
        detail = f"Python 模块缺失：{root}"
    else:
        detail = root

    message = f"无法加载 social-auto-upload 模块：{detail}。目录：{vendor_path}"
    if is_docker_runtime():
        message += f" {docker_login_hint()}"
    else:
        message += " 请确认 SAU_VENDOR_PATH 指向 vendor/social-auto-upload。"
    return message


PLATFORM_APP_NAMES = {
    "xhs": "小红书 App",
    "douyin": "抖音 App",
    "kuaishou": "快手 App",
    "bilibili": "哔哩哔哩 App",
    "channels": "微信 App",
}


def platform_scan_hint(platform: str) -> str:
    app_name = PLATFORM_APP_NAMES.get(platform, "对应平台 App")
    return f"请使用{app_name}扫码登录"


def get_runtime_info() -> dict:
    from app.workers.redis_queue import task_queue

    settings = get_settings()
    vendor_path = settings.sau_vendor_abs_path
    chrome_path = find_chromium_executable()
    docker = is_docker_runtime()
    return {
        "docker": docker,
        "playwright_headless": settings.playwright_headless if not docker else True,
        "chromium_available": chromium_available(),
        "chromium_executable": chrome_path,
        "sau_vendor_path": str(vendor_path),
        "sau_vendor_exists": vendor_path.exists(),
        "qr_login_supported": qr_login_supported(),
        "xhs_qr_login_supported": xhs_qr_login_supported(),
        "headless_publish_supported": headless_publish_supported(),
        "docker_login_hint": docker_login_hint() if docker else "",
        "local_app_url": "http://127.0.0.1:8765/app/",
        "scheduler_enabled": settings.scheduler_enabled,
        "scheduler_poll_interval_seconds": settings.scheduler_poll_interval_seconds,
        "task_queue_enabled": settings.task_queue_enabled,
        "task_queue_embedded_consumer": settings.task_queue_embedded_consumer,
        "redis_connected": task_queue.ping(),
        "storage": settings.storage,
        "bilibili_enabled": settings.bilibili_enabled,
    }
