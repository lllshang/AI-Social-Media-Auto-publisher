#!/usr/bin/env python3
"""校验已注册平台 Adapter 可导入（E.5.9 API 链路前置检查）。"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

PLATFORMS = ["xhs", "douyin", "kuaishou", "channels", "bilibili"]


def main() -> None:
    from app.adapters.factory import get_adapter_factory

    factory = get_adapter_factory()
    for platform in PLATFORMS:
        adapter = factory.get_platform_adapter(platform)
        print(f"[ok] {platform} -> {adapter.__class__.__name__}")
    print(f"\n共 {len(PLATFORMS)} 个平台 Adapter 注册正常")


if __name__ == "__main__":
    main()
