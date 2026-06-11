#!/usr/bin/env bash
# 双击此文件：若已配置 worker.env 则直接启动，否则进入交互配置
cd "$(dirname "$0")"
if [[ -f worker.env ]] && grep -q 'AI_PUBLISH_WORKER_TOKEN=.' worker.env 2>/dev/null; then
  exec ./run-worker.sh
else
  exec ./bootstrap-local.sh
fi
