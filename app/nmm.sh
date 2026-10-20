#!/bin/sh
# Nature-Mirror Mesh — one-command launcher.
#
#   sh nmm.sh [port]
#
# Starts the Post Office (propagation node) if it is not already
# running, then starts the app. Open the printed URL in your browser.
#
# PYTHON can be overridden, e.g.:  PYTHON=python3 sh nmm.sh
set -e
cd "$(dirname "$0")"
PYTHON="${PYTHON:-python3}"
PORT="${1:-8899}"

mkdir -p data

# --- Post Office -------------------------------------------------------
if [ -f data/postoffice.pid ]; then
  PID="$(cat data/postoffice.pid)"
  if kill -0 "$PID" 2>/dev/null; then
    echo "Post Office already running (pid $PID)"
    PO_RUNNING=1
  fi
fi
if [ -z "$PO_RUNNING" ]; then
  echo "Starting Post Office…"
  nohup "$PYTHON" postoffice.py >> data/postoffice.log 2>&1 &
  echo $! > data/postoffice.pid
  sleep 2
fi

# --- App ----------------------------------------------------------------
echo "Starting Nature-Mirror Mesh app on http://127.0.0.1:$PORT"
exec "$PYTHON" nmm_app.py "$PORT"
