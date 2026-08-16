#!/usr/bin/env bash
# 本机 Worker 启动脚本（供手动运行、launchd、systemd 共用）
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$ROOT_DIR/worker/worker.env"
VENV_PYTHON="$ROOT_DIR/backend/.venv/bin/python"
WORKER_SCRIPT="$ROOT_DIR/worker/local_publish_worker.py"
LOG_DIR="$ROOT_DIR/worker/logs"

if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  set -a
  source "$ENV_FILE"
  set +a
fi

if [[ -z "${AI_PUBLISH_WORKER_TOKEN:-}" ]]; then
  echo "[worker] 错误: 请在 worker/worker.env 中设置 AI_PUBLISH_WORKER_TOKEN" >&2
  exit 1
fi

if [[ ! -x "$VENV_PYTHON" ]]; then
  echo "[worker] 错误: 未找到 $VENV_PYTHON，请先在 ai-publish 目录执行 ./start.sh 或创建 backend/.venv" >&2
  exit 1
fi

mkdir -p "$LOG_DIR"

SAU_VENDOR="$(cd "$ROOT_DIR/../vendor/social-auto-upload" && pwd)"
# 本机 Worker 强制使用项目内 vendor，覆盖 .env / 环境中的 Docker 路径（/vendor/...）
export SAU_VENDOR_PATH="$SAU_VENDOR"
export PLAYWRIGHT_HEADLESS="${PLAYWRIGHT_HEADLESS:-false}"
export PLAYWRIGHT_CHANNEL="${PLAYWRIGHT_CHANNEL:-chrome}"

if [[ -f "$SAU_VENDOR/conf.example.py" && ! -f "$SAU_VENDOR/conf.py" ]]; then
  cp "$SAU_VENDOR/conf.example.py" "$SAU_VENDOR/conf.py"
  echo "[worker] 已从 conf.example.py 生成 vendor/social-auto-upload/conf.py"
fi

echo "[worker] SAU_VENDOR_PATH=$SAU_VENDOR_PATH"

BILIUP_BIN="$("$VENV_PYTHON" -c "import sys; sys.path.insert(0, '$SAU_VENDOR'); from uploader.bilibili_uploader.runtime import build_biliup_runtime_path; print(build_biliup_runtime_path())" 2>/dev/null || true)"
if [[ -n "${BILIUP_BIN:-}" && ! -x "$BILIUP_BIN" ]]; then
  echo "[worker] 警告: 本机未安装 biliup，B 站发布前请执行: bash worker/install-biliup-local.sh" >&2
fi

POLL_TIMEOUT="${AI_PUBLISH_WORKER_POLL_TIMEOUT:-30}"
API_BASE="${AI_PUBLISH_API_BASE:-http://127.0.0.1:8765}"

exec "$VENV_PYTHON" "$WORKER_SCRIPT" \
  --api-base "$API_BASE" \
  --token "$AI_PUBLISH_WORKER_TOKEN" \
  --poll-timeout "$POLL_TIMEOUT"
