#!/usr/bin/env bash
# WebForge AI — Start Script (macOS/Linux). Equivalent of start.ps1: brings
# up the backend and frontend from one command, streaming both logs here.
# Ctrl-C stops both. Ollama is NOT started for you — run `ollama serve`
# yourself first (same as the PowerShell script requires).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "\033[36mStarting WebForge AI...\033[0m"

pids=()
cleanup() {
  echo ""
  echo "Shutting down..."
  for pid in "${pids[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# Backend — binds to 127.0.0.1 by default (see backend/.env / HOST). This
# app has no authentication; do not change HOST to 0.0.0.0 unless you
# understand that exposes it, unauthenticated, to your whole network.
(
  cd "$SCRIPT_DIR/backend"
  python -m app.main
) &
pids+=($!)

sleep 2

(
  cd "$SCRIPT_DIR/frontend"
  npm run dev
) &
pids+=($!)

echo ""
echo -e "\033[32mWebForge AI is starting up:\033[0m"
echo "  Frontend : http://localhost:5173"
echo "  Backend  : http://127.0.0.1:8000 (loopback only, no auth)"
echo "  API Docs : http://127.0.0.1:8000/docs"
echo ""
echo -e "\033[33mMake sure Ollama is running: ollama serve\033[0m"
echo ""
echo "Press Ctrl-C to stop both."

wait
