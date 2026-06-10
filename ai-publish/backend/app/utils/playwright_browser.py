import os
from functools import lru_cache
from pathlib import Path

SYSTEM_CHROMIUM_CANDIDATES = (
    "/usr/bin/chromium",
    "/usr/lib/chromium/chromium",
    "/usr/bin/chromium-browser",
    "/usr/bin/google-chrome-stable",
)

DOCKER_CHROMIUM_ARGS = (
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
)


@lru_cache
def find_chromium_executable() -> str:
    configured = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE", "").strip()
    if configured and Path(configured).exists():
        return configured

    for path in SYSTEM_CHROMIUM_CANDIDATES:
        candidate = Path(path)
        if candidate.is_file():
            return str(candidate)

    roots = []
    browsers_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "").strip()
    if browsers_path:
        roots.append(Path(browsers_path))
    roots.extend(
        [
            Path("/opt/playwright"),
            Path.home() / ".cache" / "ms-playwright",
        ]
    )

    preferred_names = ("chrome-headless-shell", "chrome")
    for root in roots:
        if not root.exists():
            continue
        for name in preferred_names:
            for candidate in root.rglob(name):
                if candidate.is_file():
                    return str(candidate)
    return ""


def chromium_available() -> bool:
    return bool(find_chromium_executable())


def is_docker_runtime() -> bool:
    return Path("/.dockerenv").exists()


def build_chromium_launch_kwargs(*, headless: bool) -> dict:
    """Build patchright/playwright chromium.launch kwargs for local or Docker."""
    kwargs: dict = {"headless": headless}
    executable = find_chromium_executable()
    if executable:
        kwargs["executable_path"] = executable
    else:
        channel = os.environ.get("PLAYWRIGHT_CHANNEL", "chrome").strip()
        if channel:
            kwargs["channel"] = channel

    args = list(kwargs.get("args", []))
    if is_docker_runtime():
        for flag in DOCKER_CHROMIUM_ARGS:
            if flag not in args:
                args.append(flag)
    if args:
        kwargs["args"] = args
    return kwargs
