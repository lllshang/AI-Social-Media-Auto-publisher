#!/usr/bin/env bash
# 在 API 容器内预下载 biliup（B 站登录/发布依赖），避免首次扫码长时间卡在「检查组件」
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

if ! docker compose ps api --status running 2>/dev/null | grep -q api; then
  echo "[biliup] 错误: api 容器未运行，请先 docker compose up -d api"
  exit 1
fi

echo "[biliup] 在 API 容器内下载/校验 biliup（首次约 30–120 秒，取决于 GitHub 网络）..."
docker compose exec -T api python -u - <<'PY'
import sys
import time

sys.path.insert(0, "/vendor/social-auto-upload")
from uploader.bilibili_uploader.runtime import build_biliup_runtime_path, ensure_biliup_binary

def on_progress(message: str) -> None:
    print(f"[biliup] {message}", flush=True)

target = build_biliup_runtime_path()
print(f"[biliup] 目标: {target}", flush=True)
if target.exists():
    print(f"[biliup] 已存在: {target}", flush=True)
else:
    print("[biliup] 本地无缓存，开始从镜像/GitHub 下载…", flush=True)
started = time.time()
path = ensure_biliup_binary(force_check=False, progress_callback=on_progress)
elapsed = int(time.time() - started)
print(f"[biliup] 就绪: {path} （耗时 {elapsed}s）", flush=True)
PY

echo "[biliup] 完成。可刷新平台账号页重新扫码登录。"
