#!/bin/bash
set -e

cd "$(dirname "$0")/.."

if ! command -v podman >/dev/null 2>&1; then
  echo "podman not found. Install it first: apt install podman podman-compose"
  exit 1
fi

# Build the base chat environment image.
./scripts/build-chat-image.sh

# Start PostgreSQL+pgvector.
podman-compose -f infra/compose.yml up -d postgres

echo "Setup complete. Run 'scripts/run-backend.sh' and 'scripts/run-frontend.sh'."
