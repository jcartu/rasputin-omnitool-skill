#!/usr/bin/env bash
# Start the agent-infra/sandbox container for PHASE-3+ testing.
set -euo pipefail

NAME="become-manus-sandbox"
PORT="${1:-8080}"

# Stop existing container if running
docker rm -f "$NAME" 2>/dev/null || true

echo "Starting $NAME on port $PORT..."
docker run --rm -d \
  --name "$NAME" \
  -p "$PORT":8080 -p "${PORT}8200":8200 -p "${PORT}8888":8888 \
  -v /tmp/become-manus-sandbox-volume:/workspace \
  ghcr.io/agent-infra/sandbox:latest

echo "Waiting for sandbox to be ready..."
for i in $(seq 1 30); do
  if curl -sf "http://127.0.0.1:$PORT/v1/health" >/dev/null 2>&1; then
    echo "Sandbox is ready on http://127.0.0.1:$PORT"
    exit 0
  fi
  sleep 1
done

echo "ERROR: Sandbox failed to start within 30s"
docker logs "$NAME" 2>&1 | tail -20
exit 1
