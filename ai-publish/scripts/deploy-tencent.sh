#!/usr/bin/env bash
# 腾讯云 / Linux 服务器一键部署（配置见 scripts/deploy.env）
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/scripts/deploy.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "请先复制并编辑配置："
  echo "  cp scripts/deploy.env.example scripts/deploy.env"
  exit 1
fi

# shellcheck disable=SC1090
source "$ENV_FILE"

PUBLIC_HOST="${PUBLIC_HOST:?请在 deploy.env 中设置 PUBLIC_HOST}"
USE_HTTPS="${USE_HTTPS:-false}"
API_PORT="${API_PORT:-8000}"
INSTALL_DIR="${INSTALL_DIR:-/opt/ai-publish}"
USE_CN_MIRROR="${USE_CN_MIRROR:-true}"

if [[ "$USE_HTTPS" == "true" ]]; then
  PUBLIC_URL="https://${PUBLIC_HOST}"
else
  if [[ "$API_PORT" == "80" ]]; then
    PUBLIC_URL="http://${PUBLIC_HOST}"
  else
    PUBLIC_URL="http://${PUBLIC_HOST}:${API_PORT}"
  fi
fi

echo "=========================================="
echo " AI Publish 部署"
echo " 访问地址: ${PUBLIC_URL}/app/"
echo " 配置目录: ${ENV_FILE}"
echo "=========================================="

# 2G 内存建议 swap
if [[ "$(free -m | awk '/^Mem:/{print $2}')" -lt 3500 ]]; then
  if ! swapon --show | grep -q /swapfile; then
    echo "[可选] 内存 < 4G，建议启用 swap（需 sudo）"
  fi
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "未检测到 Docker，请先安装："
  echo "  bash scripts/install-docker-ubuntu.sh"
  exit 1
fi

if ! docker compose version >/dev/null 2>&1 && ! command -v docker-compose >/dev/null 2>&1; then
  echo "未检测到 docker compose，请执行："
  echo "  bash scripts/install-docker-ubuntu.sh"
  exit 1
fi

if [[ "$USE_CN_MIRROR" == "true" ]]; then
  echo "[镜像] 预拉取国内镜像..."
  docker pull docker.m.daocloud.io/library/mysql:8.0 && docker tag docker.m.daocloud.io/library/mysql:8.0 mysql:8.0 || true
  docker pull docker.m.daocloud.io/library/python:3.11-slim && docker tag docker.m.daocloud.io/library/python:3.11-slim python:3.11-slim || true
  docker pull docker.m.daocloud.io/library/redis:7-alpine && docker tag docker.m.daocloud.io/library/redis:7-alpine redis:7-alpine || true
fi

cd "$ROOT_DIR"

if [[ ! -f .env ]]; then
  cp .env.docker.example .env
fi

# 生成/更新 .env 中与对外访问相关的项（不覆盖已有密钥时可手工维护 .env）
grep -q '^API_PORT=' .env 2>/dev/null && sed -i.bak "s/^API_PORT=.*/API_PORT=${API_PORT}/" .env || echo "API_PORT=${API_PORT}" >> .env

if [[ ! -d web/dist ]]; then
  echo "[前端] 构建 web/dist ..."
  if command -v npm >/dev/null 2>&1; then
    (cd web && npm ci && npm run build)
  else
    echo "未安装 Node.js，请在本机构建 web/dist 后上传到服务器"
    exit 1
  fi
fi

echo "[Docker] docker compose up ..."
docker compose up -d --build

echo "[Playwright] 安装浏览器（扫码登录，可单独重试）..."
if bash scripts/install-playwright-browser.sh; then
  echo "[Playwright] 浏览器就绪"
else
  echo "[Playwright] 浏览器安装未完成，稍后可执行: bash scripts/install-playwright-browser.sh"
fi

echo ""
echo "部署完成。"
echo "  管理后台: ${PUBLIC_URL}/app/"
echo "  健康检查: ${PUBLIC_URL}/health"
echo ""
echo "换 IP 或域名：编辑 ${ENV_FILE} 中的 PUBLIC_HOST，必要时改 USE_HTTPS / API_PORT，再执行："
echo "  bash scripts/deploy-tencent.sh"
