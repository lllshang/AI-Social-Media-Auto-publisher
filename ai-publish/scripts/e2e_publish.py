#!/usr/bin/env python3
"""ai-publish 平台端到端发布脚本（API 链路）。"""

from __future__ import annotations

import json
import shutil
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

BASE = "http://127.0.0.1:8765"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SAU_COOKIE = PROJECT_ROOT / "vendor/social-auto-upload/cookies/xiaohongshu_test1.json"


def api(method: str, path: str, token: str | None = None, body: dict | None = None) -> dict:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{BASE}{path}", data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.loads(resp.read())


def import_cookie(account_name: str = "test1") -> int:
    from app.database import SessionLocal
    from app.models import AccountCookie, PlatformAccount
    from app.services.platform_account_service import PlatformAccountService

    if not SAU_COOKIE.exists():
        raise FileNotFoundError(f"找不到 Cookie: {SAU_COOKIE}")

    db = SessionLocal()
    try:
        service = PlatformAccountService(db)
        account = (
            db.query(PlatformAccount)
            .filter(PlatformAccount.platform == "xhs", PlatformAccount.account_name == account_name)
            .first()
        )
        if not account:
            account = service.create_account("xhs", account_name)
            print(f"[1] 创建平台账号 id={account.id}")
        else:
            print(f"[1] 使用已有平台账号 id={account.id}")

        db.query(AccountCookie).filter(AccountCookie.account_id == account.id).delete()
        db.commit()

        cookie_plain = SAU_COOKIE.read_text(encoding="utf-8")
        service.save_cookie(account, cookie_plain)
        cookie_file = Path(service.cookie_file_path(account))
        cookie_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SAU_COOKIE, cookie_file)
        print(f"[2] Cookie 已导入: {cookie_file}")
        return account.id
    finally:
        db.close()


def upload_material(token: str, image_path: Path) -> int:
    import mimetypes
    from urllib.request import Request, urlopen

    boundary = "----AiPublishBoundary"
    mime = mimetypes.guess_type(str(image_path))[0] or "application/octet-stream"
    file_bytes = image_path.read_bytes()
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{image_path.name}"\r\n'
        f"Content-Type: {mime}\r\n\r\n"
    ).encode() + file_bytes + f"\r\n--{boundary}--\r\n".encode()
    req = Request(
        f"{BASE}/api/materials/upload",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    with urlopen(req, timeout=120) as resp:
        material = json.loads(resp.read())
    return material["id"]


def main() -> None:
    print("=== ai-publish API 端到端发布 ===\n")

    token = api("POST", "/api/auth/login", body={"username": "admin", "password": "admin123"})[
        "access_token"
    ]
    print("[0] API 登录 OK")

    account_id = import_cookie("test1")

    check = api("POST", f"/api/platform-accounts/{account_id}/check-cookie", token=token)
    print(f"[3] Cookie 校验: {check}")
    if not check.get("valid"):
        print("Cookie 无效，请在 /docs 调用 login 接口扫码后再试")
        sys.exit(1)

    text = api(
        "POST",
        "/api/ai/text/generate",
        token=token,
        body={"topic": "AI平台API发布测试", "platform": "xhs"},
    )
    print(f"[4] AI 文案: title={text['title']!r}")

    demo_image = PROJECT_ROOT / "vendor/social-auto-upload/videos/demo.png"
    material_id = upload_material(token, demo_image)
    print(f"[5] 上传素材 id={material_id} file={demo_image.name}")

    task = api(
        "POST",
        "/api/publish-tasks",
        token=token,
        body={
            "title": text["title"],
            "content": text["content"],
            "tags": text["tags"],
            "platform": "xhs",
            "account_id": account_id,
            "content_type": "note",
            "material_ids": [material_id],
            "submit": True,
        },
    )
    task_id = task["id"]
    print(f"[6] 发布任务已创建 id={task_id} status={task['status']}")

    print("[7] 触发发布（会打开 Chrome，请稍候）...")
    api("POST", f"/api/publish-tasks/{task_id}/execute", token=token)

    for i in range(60):
        time.sleep(3)
        task = api("GET", f"/api/publish-tasks/{task_id}", token=token)
        logs = api("GET", f"/api/publish-tasks/{task_id}/logs", token=token)
        status = task["status"]
        print(f"  ... status={status} logs={len(logs)}")
        if status in {"success", "failed"}:
            print(f"\n[8] 最终结果: {status}")
            if task.get("error_message"):
                print(f"    错误: {task['error_message']}")
            print("    日志:")
            for log in logs:
                print(f"      - [{log['step']}] {log['status']}: {log.get('message')}")
            break
    else:
        print("超时，请手动查看 /docs 或 logs 接口")


if __name__ == "__main__":
    main()
