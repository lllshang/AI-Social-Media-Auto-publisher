"""账号级发布代理 URL 解析与 Playwright / biliup 适配。"""

from __future__ import annotations

from urllib.parse import urlparse, urlunparse


def validate_proxy_url(proxy_url: str) -> str:
    value = (proxy_url or "").strip()
    if not value:
        return ""
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https", "socks5"}:
        raise ValueError("网络线路须为 http://、https:// 或 socks5:// 开头的地址")
    if not parsed.hostname:
        raise ValueError("网络线路地址无效，请检查主机名")
    if not parsed.port:
        raise ValueError("网络线路须包含端口号，例如 :8080")
    return value


def mask_proxy_url(proxy_url: str | None) -> str | None:
    if not proxy_url:
        return None
    parsed = urlparse(proxy_url.strip())
    if not parsed.hostname:
        return "已配置"
    host = parsed.hostname
    if parsed.port:
        host = f"{host}:{parsed.port}"
    scheme = parsed.scheme or "http"
    return f"{scheme}://{host}"


def to_playwright_proxy(proxy_url: str | None) -> dict[str, str] | None:
    value = (proxy_url or "").strip()
    if not value:
        return None
    parsed = urlparse(value)
    if not parsed.hostname or not parsed.port:
        return None
    server = f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"
    result: dict[str, str] = {"server": server}
    if parsed.username:
        result["username"] = parsed.username
    if parsed.password:
        result["password"] = parsed.password
    return result


def to_biliup_proxy_arg(proxy_url: str | None) -> str | None:
    value = (proxy_url or "").strip()
    return value or None


def build_biliup_arguments(base_args: list[str], proxy_url: str | None) -> list[str]:
    proxy = to_biliup_proxy_arg(proxy_url)
    if not proxy:
        return base_args
    return ["-p", proxy, *base_args]
