#!/bin/bash
# Start the e-sign server + Cloudflare tunnel
# Usage: ./start.sh

set -e
cd "$(dirname "$0")"

echo "Starting e-sign server on port 8420..."
~/.local/bin/uv run python run.py &
SERVER_PID=$!

sleep 2

echo "Starting Cloudflare tunnel..."
~/.local/bin/cloudflared tunnel --url http://localhost:8420 2>&1 | tee /tmp/cloudflared.log &
TUNNEL_PID=$!

sleep 5
TUNNEL_URL=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' /tmp/cloudflared.log | head -1)

if [ -n "$TUNNEL_URL" ]; then
  echo ""
  echo "========================================"
  echo "  E-Sign server is live!"
  echo "  Local:  http://localhost:8420"
  echo "  Public: $TUNNEL_URL"
  echo "========================================"
  echo ""
  # Update .env with new tunnel URL
  sed -i '' "s|ESIGN_BASE_URL=.*|ESIGN_BASE_URL=$TUNNEL_URL|" .env
  echo "Updated .env with tunnel URL"
else
  echo "Warning: Could not detect tunnel URL. Check /tmp/cloudflared.log"
fi

echo "Press Ctrl+C to stop both services."

cleanup() {
  echo "Shutting down..."
  kill $SERVER_PID $TUNNEL_PID 2>/dev/null
  exit
}
trap cleanup SIGINT SIGTERM

wait
