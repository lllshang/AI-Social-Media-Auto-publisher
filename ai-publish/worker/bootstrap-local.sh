#!/usr/bin/env bash
# 交互式：写入 worker.env 并启动本机 Worker（在 Mac「终端」里执行）
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
WORKER_DIR="$ROOT_DIR/worker"
ENV_FILE="$WORKER_DIR/worker.env"

echo "=== AI Publish 本机 Worker 配置 ==="
echo ""
echo "说明：「服务器地址」= 你打开管理后台时浏览器地址栏里的地址（不是本机域名）。"
echo "      例如本地开发：http://127.0.0.1:8765"
echo "      例如云服务器：https://publish.example.com"
echo ""

read -r -p "服务器地址 [http://127.0.0.1:8765]: " API_BASE
API_BASE="${API_BASE:-http://127.0.0.1:8765}"
API_BASE="${API_BASE%/}"

read -r -p "Worker Token（系统设置里复制的）: " TOKEN
if [[ -z "$TOKEN" ]]; then
  echo "Token 不能为空" >&2
  exit 1
fi

cat > "$ENV_FILE" <<EOF
AI_PUBLISH_API_BASE=$API_BASE
AI_PUBLISH_WORKER_TOKEN=$TOKEN
EOF
chmod 600 "$ENV_FILE"
echo ""
echo "已写入 $ENV_FILE"
echo "正在启动 Worker（Ctrl+C 可停止）..."
echo ""

exec "$WORKER_DIR/run-worker.sh"
