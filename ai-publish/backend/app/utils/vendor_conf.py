"""确保 social-auto-upload vendor 可导入（sys.path + conf 模块）。"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from types import ModuleType

from loguru import logger

from app.config import BACKEND_DIR, get_settings


def _default_vendor_path() -> Path:
    return (BACKEND_DIR.parent.parent / "vendor" / "social-auto-upload").resolve()


def vendor_root() -> Path:
    configured = get_settings().sau_vendor_abs_path
    if configured.exists():
        return configured
    fallback = _default_vendor_path()
    if fallback.exists():
        logger.warning(
            "SAU_VENDOR_PATH 配置的路径不存在（{}），已回退到 {}",
            configured,
            fallback,
        )
        return fallback
    return configured


def ensure_vendor_on_path() -> Path:
    vendor = vendor_root()
    if not vendor.exists():
        raise RuntimeError(
            f"未找到 social-auto-upload 目录：{vendor}。"
            "请检查 SAU_VENDOR_PATH 环境变量或配置。"
        )
    vendor_str = str(vendor)
    if vendor_str not in sys.path:
        sys.path.insert(0, vendor_str)
    return vendor


def ensure_conf_file(vendor: Path | None = None) -> Path:
    root = vendor or vendor_root()
    conf_path = root / "conf.py"
    example_path = root / "conf.example.py"
    if not conf_path.exists():
        if not example_path.exists():
            raise RuntimeError(
                f"缺少 {conf_path} 且未找到 {example_path}。"
                "请在 vendor/social-auto-upload 下执行：cp conf.example.py conf.py"
            )
        shutil.copy2(example_path, conf_path)
        logger.info("已从 conf.example.py 生成 {}", conf_path)
    return conf_path


def configure_vendor_runtime() -> ModuleType:
    """将 ai-publish 运行参数写入 vendor 的 conf 模块。"""
    vendor = ensure_vendor_on_path()
    ensure_conf_file(vendor)
    import conf  # type: ignore

    from app.utils.playwright_browser import find_chromium_executable, is_docker_runtime

    settings = get_settings()
    headless = settings.playwright_headless
    if is_docker_runtime():
        headless = True
    conf.LOCAL_CHROME_HEADLESS = headless

    chrome_path = find_chromium_executable()
    if chrome_path:
        conf.LOCAL_CHROME_PATH = chrome_path
    elif is_docker_runtime():
        logger.warning("Docker 环境未找到 Chromium，扫码/发布可能失败")

    if not hasattr(conf, "PLAYWRIGHT_PROXY"):
        conf.PLAYWRIGHT_PROXY = None
    return conf
