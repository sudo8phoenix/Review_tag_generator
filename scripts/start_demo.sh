#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
if [ ! -x .venv/bin/python ] || [ ! -d frontend/node_modules ]; then
  echo 'Install Python dependencies in .venv and run npm install in frontend first.'
  exit 1
fi
PYTHONPATH=src .venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 &
demo_backend_pid=$!
trap 'kill "$demo_backend_pid" 2>/dev/null || true' EXIT INT TERM
npm --prefix frontend run dev -- --port 5173 --strictPort
