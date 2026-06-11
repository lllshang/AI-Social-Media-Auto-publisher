#!/usr/bin/env python3
"""ai-publish 平台端到端发布脚本（API 链路）。"""

from __future__ import annotations

import argparse
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

PLATFORM_CONFIG = {
    "xhs": {
        "label": "小红书",
        "cookie_candidates": [
            PROJECT_ROOT / "vendor/social-auto-upload/cookies/xiaohongshu_test1.json",
            PROJECT_ROOT / "vendor/social-auto-upload/cookies/xhs_uploader/account.json",
        ],
        "default_account": "test1",
        "content_types": ("note", "video"),
    },
    "douyin": {
        "label": "抖音",
        "cookie_candidates": [
            PROJECT_ROOT / "vendor/social-auto-upload/cookies/douyin_uploader/account.json",
            PROJECT_ROOT / "vendor/social-auto-upload/cookies/douyin.json",
        ],
        "default_account": "douyin_test",
        "content_types": ("note", "video"),
    },
    "kuaishou": {
        "label": "快手",
        "cookie_candidates": [
            PROJECT_ROOT / "vendor/social-auto-upload/cookies/ks_uploader/account.json",
            PROJECT_ROOT / "vendor/social-auto-upload/cookies/kuaishou.json",
        ],
        "default_account": "kuaishou_test",
        "content_types": ("note", "video"),
    },
}


def api(method: str, path: str, token: str | None = None, body: dict | None = None) -> dict:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{BASE}{path}", data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.loads(resp.read())


def resolve_cookie_path(platform: str, cookie_arg: str | None) -> Path:
    if cookie_arg:
        path = Path(cookie_arg).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"Cookie 文件不存在: {path}")
        return path
    for candidate in PLATFORM_CONFIG[platform]["cookie_candidates"]:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"未找到 {PLATFORM_CONFIG[platform]['label']} Cookie，请通过 --cookie 指定，"
        f"或在 vendor/social-auto-upload 下导入 Cookie"
    )


def import_cookie(platform: str, account_name: str, cookie_path: Path) -> int:
    from app.database import SessionLocal
    from app.models import AccountCookie, PlatformAccount
    from app.services.platform_account_service import PlatformAccountService

    db = SessionLocal()
    try:
        service = PlatformAccountService(db)
        account = (
            db.query(PlatformAccount)
            .filter(PlatformAccount.platform == platform, PlatformAccount.account_name == account_name)
            .first()
        )
        if not account:
            account = service.create_account(platform, account_name)
            print(f"[1] 创建平台账号 id={account.id} platform={platform}")
        else:
            print(f"[1] 使用已有平台账号 id={account.id} platform={platform}")

        db.query(AccountCookie).filter(AccountCookie.account_id == account.id).delete()
        db.commit()

        cookie_plain = cookie_path.read_text(encoding="utf-8")
        service.save_cookie(account, cookie_plain)
        cookie_file = Path(service.cookie_file_path(account))
        cookie_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(cookie_path, cookie_file)
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ai-publish 多平台 E2E 发布脚本")
    parser.add_argument("--platform", choices=PLATFORM_CONFIG.keys(), default="xhs")
    parser.add_argument("--content-type", choices=("note", "video"), default="note")
    parser.add_argument("--account", default=None, help="平台账号名，默认按平台预设")
    parser.add_argument("--cookie", default=None, help="Cookie JSON 文件路径")
    parser.add_argument("--topic", default="AI平台API发布测试")
    parser.add_argument("--skip-execute", action="store_true", help="仅验证 API 链路，不触发 Playwright 发布")
    parser.add_argument("--base-url", default=BASE)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    global BASE
    BASE = args.base_url.rstrip("/")

    platform = args.platform
    cfg = PLATFORM_CONFIG[platform]
    account_name = args.account or cfg["default_account"]
    content_type = args.content_type

    print(f"=== ai-publish E2E | {cfg['label']} | {content_type} ===\n")

    token = api("POST", "/api/auth/login", body={"username": "admin", "password": "admin123"})[
        "access_token"
    ]
    print("[0] API 登录 OK")

    cookie_path = resolve_cookie_path(platform, args.cookie)
    account_id = import_cookie(platform, account_name, cookie_path)

    check = api("POST", f"/api/platform-accounts/{account_id}/check-cookie", token=token)
    print(f"[3] Cookie 校验: {check}")
    if not check.get("valid"):
        print("Cookie 无效，请扫码登录或重新导入 Cookie 后再试")
        sys.exit(1)

    text = api(
        "POST",
        "/api/ai/text/generate",
        token=token,
        body={"topic": args.topic, "platform": platform, "content_type": content_type},
    )
    print(f"[4] AI 文案: title={text['title']!r}")

    demo_image = PROJECT_ROOT / "vendor/social-auto-upload/videos/demo.png"
    if not demo_image.exists():
        raise FileNotFoundError(f"演示图片不存在: {demo_image}")
    material_id = upload_material(token, demo_image)
    print(f"[5] 上传素材 id={material_id} file={demo_image.name}")

    material_ids = [material_id]
    if content_type == "video":
        demo_video = PROJECT_ROOT / "vendor/social-auto-upload/videos/demo.mp4"
        if demo_video.exists():
            video_id = upload_material(token, demo_video)
            material_ids = [video_id]
            print(f"[5b] 上传视频素材 id={video_id}")
        else:
            print("[5b] 未找到 demo.mp4，视频任务将仅使用图片素材（可能发布失败）")

    task = api(
        "POST",
        "/api/publish-tasks",
        token=token,
        body={
            "title": text["title"],
            "content": text["content"],
            "tags": text["tags"],
            "platform": platform,
            "account_id": account_id,
            "content_type": content_type,
            "material_ids": material_ids,
            "submit": True,
        },
    )
    task_id = task["id"]
    print(f"[6] 发布任务已创建 id={task_id} status={task['status']}")

    if task["status"] == "pending_review":
        print("[6b] 任务进入待审核，自动通过审核...")
        task = api("POST", f"/api/publish-tasks/{task_id}/approve", token=token)
        print(f"     审核后 status={task['status']}")

    if args.skip_execute:
        print("[7] 已跳过执行（--skip-execute）")
        return

    print("[7] 触发发布（会打开 Chrome，请稍候）...")
    api("POST", f"/api/publish-tasks/{task_id}/execute", token=token)

    for _ in range(60):
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
