#!/usr/bin/env python3
"""将 vendor/social-auto-upload 已有 Cookie 导入 ai-publish 平台账号。"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.config import get_settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import PlatformAccount  # noqa: E402
from app.services.platform_account_service import PlatformAccountService  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = PROJECT_ROOT / "vendor/social-auto-upload/cookies/xiaohongshu_test1.json"


def main() -> None:
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SOURCE
    account_name = sys.argv[2] if len(sys.argv) > 2 else "test1"

    if not source.exists():
        print(f"Cookie 文件不存在: {source}")
        sys.exit(1)

    settings = get_settings()
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
            print(f"已创建平台账号 id={account.id} name={account_name}")

        cookie_plain = source.read_text(encoding="utf-8")
        json.loads(cookie_plain)  # validate json
        service.save_cookie(account, cookie_plain)

        cookie_file = Path(service.cookie_file_path(account))
        cookie_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, cookie_file)

        print(f"Cookie 已导入账号 id={account.id}")
        print(f"  DB 加密存储: OK")
        print(f"  文件路径: {cookie_file}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
