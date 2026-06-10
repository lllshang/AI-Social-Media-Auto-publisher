#!/usr/bin/env bash
# 检查/确保容器内 Chromium 可用（优先系统 apt 包，不再依赖 Playwright 在线下载）
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

if ! docker compose ps api >/dev/null 2>&1; then
  echo "请先启动服务: docker compose up -d"
  exit 1
fi

echo "=========================================="
echo " 检查 Chromium（小红书扫码用）"
echo " 使用系统 apt 安装，无需下载 167MB Playwright 包"
echo "=========================================="

docker compose run --rm --no-deps api bash -s <<'EOF'
set -euo pipefail

find_chrome() {
  for p in /usr/bin/chromium /usr/lib/chromium/chromium /usr/bin/chromium-browser; do
    if [[ -x "$p" ]]; then
      echo "$p"
      return 0
    fi
  done
  find /opt/playwright -type f \( -name chrome -o -name chrome-headless-shell \) 2>/dev/null | head -1
}

existing="$(find_chrome || true)"
if [[ -n "$existing" ]]; then
  echo "[chromium] 已就绪: $existing"
  exit 0
fi

echo "[chromium] 未找到，尝试 apt 安装..."
apt-get update && apt-get install -y --no-install-recommends chromium

existing="$(find_chrome || true)"
if [[ -n "$existing" ]]; then
  echo "[chromium] 安装成功: $existing"
  exit 0
fi

echo "[chromium] 仍不可用，请重建 API 镜像: bash scripts/upgrade.sh"
exit 1
EOF

echo ""
echo "[chromium] 重启 API 容器..."
docker compose restart api

echo ""
echo "完成。请打开管理后台 → 平台账号 → 扫码登录 测试。"
