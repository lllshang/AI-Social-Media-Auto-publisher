from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse


def _cache_headers(file_path: Path) -> dict[str, str]:
    # index.html 必须 no-store，避免 build 后浏览器拿着旧 HTML 引用不到新 chunk hash
    if file_path.name == "index.html":
        return {"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"}
    # JS / CSS：文件本身带 hash，immutable + 一年缓存没问题
    # 加 must-revalidate 是为了在跨版本部署时，浏览器能带上 If-None-Match 重新校验 ETag
    if file_path.suffix in {".js", ".css"}:
        return {"Cache-Control": "public, max-age=31536000, immutable, must-revalidate"}
    # 其他静态资源（favicon 等）
    return {"Cache-Control": "public, max-age=3600, must-revalidate"}


def mount_web_admin(app: FastAPI, web_dist: Path) -> None:
    """Serve Vue SPA with index.html fallback for client-side routes.

    注意：这里不再用 StaticFiles mount /app/assets，
    因为 StaticFiles 不会走我们自定义的 Cache-Control 头，
    会让浏览器对 JS/CSS 走“public, max-age=31536000, immutable”但又被前端注入的
    chunk-hash 刷新把旧 hash 锁在 disk cache 里，再次 build 后页面常白。
    所有请求（包括 assets）统一走 web_spa，由 _cache_headers 注入正确头。
    """
    index_file = web_dist / "index.html"
    favicon_file = web_dist / "favicon.ico"

    @app.get("/app")
    @app.get("/app/")
    async def web_index() -> FileResponse:
        return FileResponse(index_file, headers=_cache_headers(index_file))

    # 单独给 favicon：路径是浏览器自动请求的，需要 1x1 ico 占位
    # 或者返回 204。这里直接给前端 vite 默认生成出来的 favicon.ico（如果存在）；
    # 浏览器拿到时 Content-Type 也得对，否则 404 状态会被解析为 HTML 造成
    # chrome devtools 出现 misleading 的误导报错。
    @app.get("/app/favicon.ico")
    async def web_favicon():
        if favicon_file.is_file():
            return FileResponse(favicon_file, headers={"Cache-Control": "public, max-age=86400"})
        # 没文件就返回 204 No Content，避免 SPA fallback 把它当作 index.html 返回
        from fastapi import Response
        return Response(status_code=204)

    @app.get("/app/{full_path:path}")
    async def web_spa(full_path: str) -> FileResponse:
        # 不要把 favicon.ico 当 SPA 路由处理，直接 204（防止 index.html 被当成 icon 解析）
        if full_path == "favicon.ico":
            from fastapi import Response
            return Response(status_code=204)
        target = web_dist / full_path
        if target.is_file():
            return FileResponse(target, headers=_cache_headers(target))
        return FileResponse(index_file, headers=_cache_headers(index_file))
