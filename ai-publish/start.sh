#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
VENV_DIR="$BACKEND_DIR/.venv"
PORT="${PORT:-8765}"
HOST="${HOST:-127.0.0.1}"

cd "$BACKEND_DIR"

if [[ ! -d "$VENV_DIR" ]]; then
  echo "[setup] 创建 Python 虚拟环境..."
  python3 -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

if ! python -c "import fastapi" >/dev/null 2>&1; then
  echo "[setup] 安装依赖..."
  pip install -U pip
  pip install -r requirements.txt
fi

mkdir -p data/materials data/cookies

if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi

# 本地启动：强制使用 backend 下相对路径，避免 .env 里 Docker 的 /data/... 路径
if [[ "${USE_DOCKER:-0}" != "1" ]]; then
  export DATABASE_URL="${DATABASE_URL:-sqlite:///./data/aipublish.db}"
  export STORAGE_LOCAL_PATH="./data/materials"
  export COOKIE_DIR="./data/cookies"
  export SAU_VENDOR_PATH="$ROOT_DIR/../vendor/social-auto-upload"
  # 转为绝对路径，避免 Playwright 模块加载失败
  export SAU_VENDOR_PATH="$(cd "$SAU_VENDOR_PATH" && pwd)"
fi

export PLAYWRIGHT_HEADLESS="${PLAYWRIGHT_HEADLESS:-false}"
export PLAYWRIGHT_CHANNEL="${PLAYWRIGHT_CHANNEL:-chrome}"

echo "=========================================="
echo " AI 多平台内容自动发布系统 — MVP"
echo "=========================================="
echo " API 文档:  http://${HOST}:${PORT}/docs"
echo " 管理后台:  http://${HOST}:${PORT}/app/"
echo " 健康检查:  http://${HOST}:${PORT}/health"
echo " 默认账号:  admin / admin123"
echo " 扫码模式:  PLAYWRIGHT_HEADLESS=${PLAYWRIGHT_HEADLESS}"
echo " 按 Ctrl+C 停止服务"
echo "=========================================="

exec uvicorn app.main:app --reload --host "$HOST" --port "$PORT"
