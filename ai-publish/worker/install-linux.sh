#!/usr/bin/env bash
# Linux 桌面：安装本机 Worker 用户级 systemd 自启（需图形会话 + Chrome）
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
WORKER_DIR="$ROOT_DIR/worker"
RUN_SCRIPT="$WORKER_DIR/run-worker.sh"
SERVICE_NAME="ai-publish-worker.service"
USER_UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
SERVICE_DEST="$USER_UNIT_DIR/$SERVICE_NAME"

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "此脚本仅适用于 Linux（桌面环境）" >&2
  exit 1
fi

chmod +x "$RUN_SCRIPT"
mkdir -p "$WORKER_DIR/logs" "$USER_UNIT_DIR"

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
  echo "未找到 backend/.venv，请先安装 Python 依赖（参考 ai-publish/start.sh）" >&2
  exit 1
fi

sed \
  -e "s|__AI_PUBLISH_ROOT__|$ROOT_DIR|g" \
  -e "s|__RUN_WORKER_SH__|$RUN_SCRIPT|g" \
  "$WORKER_DIR/ai-publish-worker.service.template" > "$SERVICE_DEST"

systemctl --user daemon-reload
systemctl --user enable --now "$SERVICE_NAME"

if ! systemctl --user is-enabled "$SERVICE_NAME" >/dev/null 2>&1; then
  echo "提示：若希望「未登录桌面也自启」，需启用 lingering："
  echo "  sudo loginctl enable-linger $USER"
fi

echo "已安装并启动：$SERVICE_NAME"
echo "状态：systemctl --user status $SERVICE_NAME"
echo "日志：journalctl --user -u $SERVICE_NAME -f"
echo "停止：systemctl --user stop $SERVICE_NAME"
echo "卸载：systemctl --user disable --now $SERVICE_NAME && rm $SERVICE_DEST"
