#!/bin/bash
set -e

cd "$(dirname "$0")/.."

if ! command -v podman >/dev/null 2>&1; then
  echo "podman not found. Install it first: apt install podman podman-compose"
  exit 1
fi

echo "Starting a short-lived test container..."

cid=$(podman run -d --rm \
  --name chat-harness-test \
  --userns=keep-id \
  --cap-add=SYS_ADMIN \
  --cap-add=SETUID \
  --cap-add=SETGID \
  --security-opt seccomp=unconfined \
  --security-opt apparmor=unconfined \
  --security-opt unmask=ALL \
  -p 127.0.0.1:6080:6080 \
  localhost/chat-harness-agent:latest)

cleanup() {
  echo "Cleaning up container $cid..."
  podman stop -t 5 "$cid" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "Waiting for noVNC (max 30s)..."
for _ in $(seq 1 30); do
  if curl -s http://127.0.0.1:6080 >/dev/null; then
    echo "noVNC reachable."
    break
  fi
  sleep 1
done

echo "Checking installed agents..."
podman exec "$cid" which devin
podman exec "$cid" which agy-acp
podman exec "$cid" python3 -c "from importlib.metadata import version; print(version('playwright'))"

echo "Checking rootless podman inside container..."
podman exec "$cid" podman --version
podman exec "$cid" timeout 120 podman run --rm alpine echo hi

echo "All checks passed."
