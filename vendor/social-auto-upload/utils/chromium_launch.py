"""Chromium launch kwargs for Docker (apt) and local Chrome."""

from conf import LOCAL_CHROME_PATH, PLAYWRIGHT_PROXY

_CONTAINER_ARGS = ("--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu")


def build_launch_kwargs(headless: bool) -> dict:
    launch_kwargs: dict = {"headless": headless}
    if LOCAL_CHROME_PATH:
        launch_kwargs["executable_path"] = LOCAL_CHROME_PATH
    else:
        launch_kwargs["channel"] = "chrome"
    args = list(launch_kwargs.get("args", []))
    for flag in _CONTAINER_ARGS:
        if flag not in args:
            args.append(flag)
    launch_kwargs["args"] = args
    if PLAYWRIGHT_PROXY:
        launch_kwargs["proxy"] = PLAYWRIGHT_PROXY
    return launch_kwargs
