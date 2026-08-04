#!/usr/bin/env bash
# 从 Mac 开发机同步代码到服务器（首次部署与升级共用）
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ENV_FILE="${SCRIPT_DIR}/deploy.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "请先配置 deploy.env："
  echo "  cp scripts/deploy.env.example scripts/deploy.env"
  echo "  编辑 PUBLIC_HOST、SSH 用户等"
  exit 1
fi

# shellcheck disable=SC1090
source "$ENV_FILE"

PUBLIC_HOST="${PUBLIC_HOST:?请在 deploy.env 中设置 PUBLIC_HOST}"
SSH_USER="${SSH_USER:-ubuntu}"
REMOTE_DIR="${INSTALL_DIR:-/opt/ai-publish}"

WEB_DIR="${PROJECT_ROOT}/ai-publish/web"
if [[ -d "$WEB_DIR" ]]; then
  echo "[构建] 前端 web/dist ..."
  (cd "$WEB_DIR" && npm run build)
else
  echo "警告: 未找到 web 目录，跳过前端构建"
fi

echo "同步到 ${SSH_USER}@${PUBLIC_HOST}:${REMOTE_DIR} ..."

# 说明：INSTALL_DIR 常见为 /opt/ai-publish（需 root 写权限）。
# 这里用 --rsync-path="sudo rsync" 让远端以 root 身份写入，
# 避免 ubuntu 用户对 /opt 无写权导致同步失败；同时去掉会误判退出的
# ssh mkdir 前置检查（远端已有同名 root 目录时会直接报错退出）。
RSYNC_OPTS=(-avz --progress --delete
  --rsync-path="sudo rsync"
  --exclude 'backend/.venv'
  --exclude 'backend/data'
  --exclude 'web/node_modules'
  --exclude '.env'
  --exclude '.env.local.backup')

rsync "${RSYNC_OPTS[@]}" \
  "${PROJECT_ROOT}/ai-publish/" \
  "${SSH_USER}@${PUBLIC_HOST}:${REMOTE_DIR}/ai-publish/"

rsync -avz --progress \
  --rsync-path="sudo rsync" \
  --exclude '.venv' \
  --exclude '__pycache__' \
  "${PROJECT_ROOT}/vendor/" \
  "${SSH_USER}@${PUBLIC_HOST}:${REMOTE_DIR}/vendor/"

echo ""
echo "同步完成。在服务器上执行："
echo "  cd ${REMOTE_DIR}/ai-publish"
echo "  bash scripts/upgrade.sh          # 日常升级"
echo "  # 或 bash scripts/deploy-tencent.sh  # 首次/全量"
