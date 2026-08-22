#!/bin/bash
set -e

# Install the chat agent image and PostgreSQL container.
# Run this on the Contabo VPS once after deploying the project.

cd "$(dirname "$0")/.."

# Make sure Podman is installed.
if ! command -v podman >/dev/null 2>&1; then
  echo "podman not found. Install it first: apt install podman podman-compose"
  exit 1
fi

# Build the base chat environment image.
podman build -t localhost/chat-harness-agent:latest -f containers/chat/Containerfile containers/chat

# Start PostgreSQL+pgvector.
podman-compose -f infra/compose.yml up -d postgres

echo "Setup complete. Run 'scripts/run-backend.sh' and 'scripts/run-frontend.sh'."
