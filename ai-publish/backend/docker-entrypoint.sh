#!/usr/bin/env bash
# 容器启动时，将随镜像内置的默认 data（data.default/）注入到运行时 data 目录（/app/data）。
# 仅当目标文件不存在时才写入，避免覆盖用户在旧卷中已有的配置。
set -e

DEFAULT_DIR="/app/data.default"
DATA_DIR="/app/data"

mkdir -p "$DATA_DIR"

if [ -d "$DEFAULT_DIR" ]; then
  for f in "$DEFAULT_DIR"/*; do
    [ -e "$f" ] || continue
    base="$(basename "$f")"
    if [ ! -e "$DATA_DIR/$base" ]; then
      cp -a "$f" "$DATA_DIR/$base"
      echo "[entrypoint] 已注入默认配置: $base"
    fi
  done
fi

exec "$@"
