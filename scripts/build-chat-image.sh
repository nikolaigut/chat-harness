#!/bin/bash
set -e

cd "$(dirname "$0")/.."

if ! command -v podman >/dev/null 2>&1; then
  echo "podman not found. Install it first: apt install podman podman-compose"
  exit 1
fi

podman build \
  -t localhost/chat-harness-agent:latest \
  -f containers/chat/Containerfile \
  containers/chat

echo "Built localhost/chat-harness-agent:latest"
