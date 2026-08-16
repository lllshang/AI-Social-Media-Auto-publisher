#!/usr/bin/env bash
# 在本机 Mac/Linux Worker 预装 biliup（B 站发布必需，约 30–120 秒）
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_PYTHON="${ROOT_DIR}/backend/.venv/bin/python"
SAU_VENDOR="$(cd "${ROOT_DIR}/../vendor/social-auto-upload" && pwd)"

if [[ ! -x "$VENV_PYTHON" ]]; then
  echo "[biliup] 错误: 未找到 $VENV_PYTHON，请先执行 ./start.sh" >&2
  exit 1
fi

export SAU_VENDOR_PATH="$SAU_VENDOR"
echo "[biliup] 平台: $(uname -s)/$(uname -m)"
echo "[biliup] vendor: $SAU_VENDOR"

"$VENV_PYTHON" -u - <<'PY'
import sys
import time

vendor = __import__("os").environ.get("SAU_VENDOR_PATH", "")
if vendor and vendor not in sys.path:
    sys.path.insert(0, vendor)

from uploader.bilibili_uploader.runtime import build_biliup_runtime_path, ensure_biliup_binary

def on_progress(message: str) -> None:
    print(f"[biliup] {message}", flush=True)

target = build_biliup_runtime_path()
print(f"[biliup] 目标: {target}", flush=True)
started = time.time()
path = ensure_biliup_binary(force_check=False, progress_callback=on_progress)
elapsed = int(time.time() - started)
print(f"[biliup] 就绪: {path} （耗时 {elapsed}s）", flush=True)
PY
