#!/bin/bash
# OpenScan — one command to launch everything

DIR="$(cd "$(dirname "$0")" && pwd)"
PORT=3000

echo ""
echo "  OPENSCAN — starting up..."
echo ""

# 1. Start OpenD if not already running
if ! pgrep -f "moomoo_OpenD" > /dev/null 2>&1; then
  echo "  [1/3] Starting moomoo OpenD..."
  open -a "moomoo_OpenD" 2>/dev/null || open /Applications/moomoo_OpenD.app 2>/dev/null
  # Wait for OpenD to be reachable
  for i in {1..30}; do
    if nc -z 127.0.0.1 11111 2>/dev/null; then
      echo "  [1/3] OpenD connected."
      break
    fi
    sleep 1
  done
  if ! nc -z 127.0.0.1 11111 2>/dev/null; then
    echo "  [1/3] WARNING: OpenD not responding on port 11111."
    echo "         Please log in manually, then press Enter to continue."
    read -r
  fi
else
  echo "  [1/3] OpenD already running."
fi

# 2. Kill any existing OpenScan server
if lsof -ti :$PORT > /dev/null 2>&1; then
  echo "  [2/3] Stopping old server on port $PORT..."
  kill $(lsof -ti :$PORT) 2>/dev/null
  sleep 1
fi

# 3. Start OpenScan server
echo "  [2/3] Starting OpenScan server..."
cd "$DIR"
source venv/bin/activate
python3 server.py &
SERVER_PID=$!

# Wait for server to be ready
for i in {1..10}; do
  if curl -s http://localhost:$PORT/ > /dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

echo "  [3/3] Opening dashboard..."
open "http://localhost:$PORT"

echo ""
echo "  OpenScan is running at http://localhost:$PORT"
echo "  Press Ctrl+C to stop."
echo ""

# Keep script alive so Ctrl+C kills everything
trap "kill $SERVER_PID 2>/dev/null; echo '  Stopped.'; exit 0" INT TERM
wait $SERVER_PID
