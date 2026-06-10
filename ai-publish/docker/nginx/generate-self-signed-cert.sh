#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$DIR/certs"
openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
  -keyout "$DIR/certs/server.key" \
  -out "$DIR/certs/server.crt" \
  -subj "/CN=ai-publish.local/O=AI Publish/C=CN"
echo "Self-signed cert generated in $DIR/certs"
