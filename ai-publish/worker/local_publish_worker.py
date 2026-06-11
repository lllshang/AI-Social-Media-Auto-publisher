#!/usr/bin/env python3
"""本机发布 Worker：轮询服务器认领任务，在本机 Chrome 执行发布。"""

from __future__ import annotations

import argparse
import asyncio
import os
import socket
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import httpx

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.workers.worker_publish_runner import WorkerPublishRunner  # noqa: E402


class LocalPublishWorkerClient:
    def __init__(self, api_base: str, token: str) -> None:
        self.api_base = api_base.rstrip("/")
        self.token = token
        self.hostname = socket.gethostname()
        self.runner = WorkerPublishRunner()

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    async def heartbeat(self, client: httpx.AsyncClient) -> None:
        await client.post(
            f"{self.api_base}/api/publish-workers/heartbeat",
            headers=self._headers(),
            json={"hostname": self.hostname},
            timeout=30,
        )

    async def claim(self, client: httpx.AsyncClient, timeout_seconds: int = 30) -> dict | None:
        response = await client.post(
            f"{self.api_base}/api/publish-workers/claim",
            headers=self._headers(),
            json={"hostname": self.hostname, "timeout_seconds": timeout_seconds},
            timeout=timeout_seconds + 10,
        )
        response.raise_for_status()
        payload = response.json()
        return payload.get("task")

    async def download_material(
        self,
        client: httpx.AsyncClient,
        material_id: int,
        target_dir: Path,
        filename: str,
    ) -> str:
        response = await client.get(
            f"{self.api_base}/api/publish-workers/materials/{material_id}/download",
            headers=self._headers(),
            timeout=600,
        )
        response.raise_for_status()
        path = target_dir / filename
        path.write_bytes(response.content)
        return str(path)

    async def append_log(
        self,
        client: httpx.AsyncClient,
        task_id: int,
        step: str,
        status: str,
        message: str,
    ) -> None:
        await client.post(
            f"{self.api_base}/api/publish-workers/tasks/{task_id}/logs",
            headers=self._headers(),
            json={"step": step, "status": status, "message": message},
            timeout=30,
        )

    async def finish(self, client: httpx.AsyncClient, task_id: int, success: bool, message: str) -> None:
        await client.post(
            f"{self.api_base}/api/publish-workers/tasks/{task_id}/finish",
            headers=self._headers(),
            json={"success": success, "message": message},
            timeout=30,
        )

    async def execute_bundle(self, client: httpx.AsyncClient, bundle: dict) -> None:
        task_id = int(bundle["task_id"])
        work_dir = Path(tempfile.mkdtemp(prefix=f"ai-publish-task-{task_id}-"))
        cookie_file = work_dir / "cookie.json"
        cookie_file.write_text(bundle["cookie_plain"], encoding="utf-8")

        material_paths: list[str] = []
        thumbnail_path: str | None = None
        for item in bundle.get("materials") or []:
            local_path = await self.download_material(
                client,
                int(item["id"]),
                work_dir,
                item.get("filename") or f"material-{item['id']}",
            )
            if bundle.get("content_type") == "video":
                if item.get("type") == "video":
                    material_paths.append(local_path)
                elif item.get("type") == "image" and thumbnail_path is None:
                    thumbnail_path = local_path
            else:
                material_paths.append(local_path)

        publish_time = None
        if bundle.get("publish_time"):
            publish_time = datetime.fromisoformat(bundle["publish_time"].replace("Z", "+00:00"))

        async def log_callback(step: str, status: str, message: str) -> None:
            await self.append_log(client, task_id, step, status, message)

        await self.append_log(client, task_id, "start", "running", "本机 Worker 开始执行发布")
        try:
            result = await self.runner.run(
                task_id=task_id,
                platform=bundle["platform"],
                account_id=int(bundle["account_id"]),
                account_name=bundle["account_name"],
                cookie_file=str(cookie_file),
                title=bundle["title"],
                content=bundle.get("content") or "",
                tags=bundle.get("tags") or [],
                content_type=bundle.get("content_type") or "note",
                material_paths=material_paths,
                thumbnail_path=thumbnail_path,
                cover_text=bundle.get("cover_text"),
                publish_time=publish_time,
                bilibili_tid=bundle.get("bilibili_tid"),
                publish_proxy=bundle.get("publish_proxy"),
                log_callback=log_callback,
            )
            await self.finish(client, task_id, result.success, result.message)
        except Exception as exc:
            await self.finish(client, task_id, False, str(exc))
        finally:
            for path in work_dir.glob("*"):
                try:
                    path.unlink()
                except OSError:
                    pass
            try:
                work_dir.rmdir()
            except OSError:
                pass

    async def run_forever(self, poll_timeout: int = 30) -> None:
        async with httpx.AsyncClient() as client:
            while True:
                try:
                    await self.heartbeat(client)
                    bundle = await self.claim(client, timeout_seconds=poll_timeout)
                    if bundle:
                        await self.execute_bundle(client, bundle)
                except httpx.HTTPError as exc:
                    print(f"[worker] API 错误: {exc}", file=sys.stderr)
                    await asyncio.sleep(5)
                except Exception as exc:
                    print(f"[worker] 执行异常: {exc}", file=sys.stderr)
                    await asyncio.sleep(3)


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Publish 本机发布 Worker")
    parser.add_argument(
        "--api-base",
        default=os.environ.get("AI_PUBLISH_API_BASE", "http://127.0.0.1:8765"),
        help="服务器 API 地址，如 https://your-domain.com",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("AI_PUBLISH_WORKER_TOKEN", ""),
        help="在系统设置中创建 Worker 后获得的 Token",
    )
    parser.add_argument("--poll-timeout", type=int, default=30, help="认领任务长轮询秒数")
    args = parser.parse_args()
    if not args.token:
        raise SystemExit("请通过 --token 或环境变量 AI_PUBLISH_WORKER_TOKEN 提供 Worker Token")
    client = LocalPublishWorkerClient(args.api_base, args.token)
    print(f"[worker] 已启动，连接 {args.api_base}，主机名 {client.hostname}")
    asyncio.run(client.run_forever(poll_timeout=args.poll_timeout))


if __name__ == "__main__":
    main()
