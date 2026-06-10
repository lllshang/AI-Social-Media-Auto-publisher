#!/usr/bin/env bash
# Ubuntu 22.04 / 24.04（含腾讯云轻量）安装 Docker + Compose
set -euo pipefail

if [[ "$(id -u)" -eq 0 ]]; then
  SUDO=""
else
  SUDO="sudo"
fi

echo "[1/3] apt update ..."
$SUDO apt update

echo "[2/3] 安装 Docker ..."
if apt-cache show docker-compose-v2 &>/dev/null; then
  # Ubuntu 24.04 等：插件包名为 docker-compose-v2
  $SUDO apt install -y docker.io docker-compose-v2
elif apt-cache show docker-compose-plugin &>/dev/null; then
  $SUDO apt install -y docker.io docker-compose-plugin
elif apt-cache show docker-compose &>/dev/null; then
  $SUDO apt install -y docker.io docker-compose
else
  echo "未找到 compose 包，尝试官方安装脚本 ..."
  curl -fsSL https://get.docker.com | $SUDO sh
fi

echo "[3/3] 将当前用户加入 docker 组 ..."
TARGET_USER="${SUDO_USER:-$USER}"
if id -nG "$TARGET_USER" | grep -qw docker; then
  echo "用户 $TARGET_USER 已在 docker 组"
else
  $SUDO usermod -aG docker "$TARGET_USER"
  echo "已将 $TARGET_USER 加入 docker 组，请重新 SSH 登录后生效"
fi

echo ""
docker --version || true
docker compose version 2>/dev/null || docker-compose --version 2>/dev/null || true
echo ""
echo "Docker 安装完成。若提示 permission denied，请 exit 后重新 ssh 登录。"
