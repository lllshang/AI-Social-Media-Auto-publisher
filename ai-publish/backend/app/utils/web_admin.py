from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def _cache_headers(file_path: Path) -> dict[str, str]:
    if file_path.name == "index.html":
        return {"Cache-Control": "no-cache, no-store, must-revalidate"}
    if file_path.suffix in {".js", ".css"}:
        return {"Cache-Control": "public, max-age=31536000, immutable"}
    return {"Cache-Control": "public, max-age=3600"}


def mount_web_admin(app: FastAPI, web_dist: Path) -> None:
    """Serve Vue SPA with index.html fallback for client-side routes."""
    assets_dir = web_dist / "assets"
    if assets_dir.is_dir():
        app.mount("/app/assets", StaticFiles(directory=str(assets_dir)), name="web-assets")

    index_file = web_dist / "index.html"

    @app.get("/app")
    @app.get("/app/")
    async def web_index() -> FileResponse:
        return FileResponse(index_file, headers=_cache_headers(index_file))

    @app.get("/app/{full_path:path}")
    async def web_spa(full_path: str) -> FileResponse:
        if full_path.startswith("assets/"):
            target = web_dist / full_path
        else:
            target = web_dist / full_path
        if target.is_file():
            return FileResponse(target, headers=_cache_headers(target))
        return FileResponse(index_file, headers=_cache_headers(index_file))
