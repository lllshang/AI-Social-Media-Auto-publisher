from pathlib import Path

from app.config import get_settings
from app.utils.playwright_browser import chromium_available


def is_docker_runtime() -> bool:
    return Path("/.dockerenv").exists()


def xhs_qr_login_supported() -> bool:
    if not is_docker_runtime():
        return True
    return chromium_available()


def docker_login_hint() -> str:
    if xhs_qr_login_supported():
        return (
            "服务器将以无头浏览器打开小红书登录页，二维码会显示在本页面，"
            "请使用小红书 App 扫码完成绑定。"
        )
    return (
        "服务器尚未安装 Playwright 浏览器，无法网页扫码。"
        "请重新构建 API 镜像（含 patchright install chromium），"
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

    message = f"无法加载 social-auto-upload 小红书模块：{detail}。目录：{vendor_path}"
    if is_docker_runtime():
        message += f" {docker_login_hint()}"
    else:
        message += " 请确认 SAU_VENDOR_PATH 指向 vendor/social-auto-upload。"
    return message


def get_runtime_info() -> dict:
    settings = get_settings()
    vendor_path = settings.sau_vendor_abs_path
    return {
        "docker": is_docker_runtime(),
        "playwright_headless": settings.playwright_headless,
        "chromium_available": chromium_available(),
        "sau_vendor_path": str(vendor_path),
        "sau_vendor_exists": vendor_path.exists(),
        "xhs_qr_login_supported": xhs_qr_login_supported(),
        "docker_login_hint": docker_login_hint() if is_docker_runtime() else "",
        "local_app_url": "http://127.0.0.1:8765/app/",
    }
