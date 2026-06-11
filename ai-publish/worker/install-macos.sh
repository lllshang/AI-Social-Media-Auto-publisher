#!/usr/bin/env bash
# macOS：安装本机 Worker 开机自启（用户登录后启动，需已登录图形桌面以便 Chrome 可用）
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
WORKER_DIR="$ROOT_DIR/worker"
PLIST_LABEL="com.ai-publish.local-worker"
PLIST_DEST="$HOME/Library/LaunchAgents/${PLIST_LABEL}.plist"
RUN_SCRIPT="$WORKER_DIR/run-worker.sh"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "此脚本仅适用于 macOS" >&2
  exit 1
fi

chmod +x "$RUN_SCRIPT"
mkdir -p "$WORKER_DIR/logs"

if [[ ! -f "$WORKER_DIR/worker.env" ]]; then
  cp "$WORKER_DIR/worker.env.example" "$WORKER_DIR/worker.env"
  echo "已创建 $WORKER_DIR/worker.env，请先编辑填入 API 地址与 Token，再重新执行本脚本。"
  exit 1
fi

# shellcheck disable=SC1090
source "$WORKER_DIR/worker.env"
if [[ -z "${AI_PUBLISH_WORKER_TOKEN:-}" ]]; then
  echo "请先在 worker/worker.env 中设置 AI_PUBLISH_WORKER_TOKEN" >&2
  exit 1
fi

if [[ ! -x "$ROOT_DIR/backend/.venv/bin/python" ]]; then
  echo "未找到 backend/.venv，请先在 $ROOT_DIR 执行 ./start.sh 安装依赖" >&2
  exit 1
fi

sed \
  -e "s|__AI_PUBLISH_ROOT__|$ROOT_DIR|g" \
  -e "s|__RUN_WORKER_SH__|$RUN_SCRIPT|g" \
  "$WORKER_DIR/com.ai-publish.worker.plist.template" > "$PLIST_DEST"

launchctl bootout "gui/$(id -u)/$PLIST_LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST_DEST"
launchctl enable "gui/$(id -u)/$PLIST_LABEL"
launchctl kickstart -k "gui/$(id -u)/$PLIST_LABEL"

echo "已安装并启动：$PLIST_LABEL"
echo "日志：$WORKER_DIR/logs/worker.stdout.log / worker.stderr.log"
echo "停止：launchctl bootout gui/$(id -u)/$PLIST_LABEL"
echo "卸载：launchctl bootout gui/$(id -u)/$PLIST_LABEL && rm $PLIST_DEST"
