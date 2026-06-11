"""在 vendor Playwright 调用期间注入账号代理。"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from app.utils.proxy_utils import to_playwright_proxy


@contextmanager
def use_account_proxy(proxy_url: str | None) -> Iterator[None]:
    from app.utils.vendor_conf import configure_vendor_runtime

    conf = configure_vendor_runtime()
    previous = getattr(conf, "PLAYWRIGHT_PROXY", None)
    conf.PLAYWRIGHT_PROXY = to_playwright_proxy(proxy_url)
    try:
        yield
    finally:
        conf.PLAYWRIGHT_PROXY = previous
