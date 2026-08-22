#!/bin/bash
set -e

cd "$(dirname "$0")/../backend"

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi

.venv/bin/pip install -e ".[dev]"

export PYTHONPATH=.:$PYTHONPATH
.venv/bin/python -m app
