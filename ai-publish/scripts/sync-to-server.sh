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

echo "同步到 ${SSH_USER}@${PUBLIC_HOST}:${REMOTE_DIR} ..."

ssh "${SSH_USER}@${PUBLIC_HOST}" "mkdir -p ${REMOTE_DIR}" 2>/dev/null || {
  echo ""
  echo "无法在 ${REMOTE_DIR} 创建目录（/opt 需 root 权限）。请在服务器执行一次："
  echo "  ssh ${SSH_USER}@${PUBLIC_HOST}"
  echo "  sudo mkdir -p ${REMOTE_DIR}"
  echo "  sudo chown -R ${SSH_USER}:${SSH_USER} ${REMOTE_DIR}"
  echo ""
  echo "或把 deploy.env 中 INSTALL_DIR 改为 ~/ai-publish（如 /home/ubuntu/ai-publish）"
  exit 1
}

rsync -avz --progress \
  --exclude 'backend/.venv' \
  --exclude 'backend/data' \
  --exclude 'web/node_modules' \
  --exclude '.env.local.backup' \
  "${PROJECT_ROOT}/ai-publish/" \
  "${SSH_USER}@${PUBLIC_HOST}:${REMOTE_DIR}/ai-publish/"

rsync -avz --progress \
  --exclude '.venv' \
  --exclude '__pycache__' \
  "${PROJECT_ROOT}/vendor/" \
  "${SSH_USER}@${PUBLIC_HOST}:${REMOTE_DIR}/vendor/"

echo ""
echo "同步完成。在服务器上执行："
echo "  cd ${REMOTE_DIR}/ai-publish"
echo "  bash scripts/upgrade.sh          # 日常升级"
echo "  # 或 bash scripts/deploy-tencent.sh  # 首次/全量"
