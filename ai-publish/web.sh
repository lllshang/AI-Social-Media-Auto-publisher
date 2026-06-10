#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
WEB_DIR="$ROOT_DIR/web"

cd "$WEB_DIR"

if [[ ! -d node_modules ]]; then
  echo "[web] 安装前端依赖..."
  npm install
fi

if [[ "${1:-build}" == "dev" ]]; then
  echo "[web] 开发模式: http://127.0.0.1:5173/app/"
  npm run dev
else
  echo "[web] 构建生产包..."
  npm run build
  echo "[web] 构建完成 → web/dist"
  echo "[web] 访问: http://127.0.0.1:8765/app/ （需先 ./start.sh 启动 API）"
fi
