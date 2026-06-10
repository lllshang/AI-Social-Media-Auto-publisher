import os
from functools import lru_cache
from pathlib import Path

SYSTEM_CHROMIUM_CANDIDATES = (
    "/usr/bin/chromium",
    "/usr/lib/chromium/chromium",
    "/usr/bin/chromium-browser",
    "/usr/bin/google-chrome-stable",
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
