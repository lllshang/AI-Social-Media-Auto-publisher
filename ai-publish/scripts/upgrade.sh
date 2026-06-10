#!/usr/bin/env bash
# 已部署环境的版本升级（保留 Docker 数据卷，不重复首次装机步骤）
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/scripts/deploy.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "未找到 scripts/deploy.env，请先完成首次部署："
  echo "  cp scripts/deploy.env.example scripts/deploy.env"
  echo "  bash scripts/deploy-tencent.sh"
  exit 1
fi

# shellcheck disable=SC1090
source "$ENV_FILE"

PUBLIC_HOST="${PUBLIC_HOST:?请在 deploy.env 中设置 PUBLIC_HOST}"
USE_HTTPS="${USE_HTTPS:-false}"
API_PORT="${API_PORT:-8000}"

if [[ "$USE_HTTPS" == "true" ]]; then
  PUBLIC_URL="https://${PUBLIC_HOST}"
elif [[ "$API_PORT" == "80" ]]; then
  PUBLIC_URL="http://${PUBLIC_HOST}"
else
  PUBLIC_URL="http://${PUBLIC_HOST}:${API_PORT}"
fi

echo "=========================================="
echo " AI Publish 版本升级"
echo " 访问地址: ${PUBLIC_URL}/app/"
echo " 说明: 保留 mysql/materials/cookies 等数据卷"
echo "=========================================="

if [[ ! -d "${ROOT_DIR}/web/dist" ]]; then
  echo "错误: 缺少 web/dist，请在本机构建前端后 rsync 到服务器"
  exit 1
fi

if [[ ! -d "${ROOT_DIR}/../vendor/social-auto-upload" ]]; then
  echo "警告: 未找到 ../vendor/social-auto-upload，小红书功能可能不可用"
fi

cd "$ROOT_DIR"

echo "[升级] 重建并重启 API（MySQL/Redis 不删卷）..."
docker compose up -d --build api

echo "[Playwright] 检查/安装浏览器..."
if bash scripts/install-playwright-browser.sh; then
  echo "[Playwright] 浏览器就绪"
else
  echo "[Playwright] 浏览器安装未完成，稍后可执行: bash scripts/install-playwright-browser.sh"
fi

echo ""
echo "升级完成。"
echo "  管理后台: ${PUBLIC_URL}/app/"
echo "  健康检查: ${PUBLIC_URL}/health"
echo ""
echo "若本次升级含数据库结构变更，请按版本说明执行迁移 SQL。"
echo "查看日志: docker compose logs -f api"
