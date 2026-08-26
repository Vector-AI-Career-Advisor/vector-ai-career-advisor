#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.."

# `python -m venv` puts executables in Scripts/ on Windows and bin/ everywhere
# else, regardless of which shell created the venv — so this can't be a fixed
# path if the same script is meant to run under Git Bash too (see run-project.bat).
if [ -d "$ROOT/.venv/Scripts" ]; then
  VENV_BIN="$ROOT/.venv/Scripts"
else
  VENV_BIN="$ROOT/.venv/bin"
fi

cleanup() {
  echo ""
  echo "Shutting down..."
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null
  wait "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null
  echo "Done."
}
trap cleanup SIGINT SIGTERM

echo "Starting server..."
cd "$ROOT/server/web"
"$VENV_BIN/uvicorn" main:app --reload --port 8000 &
BACKEND_PID=$!

echo "Starting client..."
cd "$ROOT/client"
npm install --silent
npm run dev &
FRONTEND_PID=$!

echo ""
echo "Server:  http://localhost:8000"
echo "Client: http://localhost:5173"
echo ""
echo "Press Ctrl+C to stop."

wait "$BACKEND_PID" "$FRONTEND_PID"
