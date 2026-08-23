#!/bin/bash
set -e

cd "$(dirname "$0")/../backend"

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi

.venv/bin/pip install -e ".[dev]"

export PYTHONPATH=.:$PYTHONPATH
# uvicorn's default uvloop reloader worker can hang on podman run -d.
export UVICORN_LOOP=asyncio
export UVICORN_RELOAD=true
.venv/bin/python -m app
