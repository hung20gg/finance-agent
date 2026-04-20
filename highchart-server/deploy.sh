#!/usr/bin/env bash
set -euo pipefail

# ─── Config ──────────────────────────────────────────────────────────────────
IMAGE_NAME="highchart_render"
CONTAINER_NAME="highchart_render"
HOST_PORT="${PORT:-3000}"

# Pool / performance settings (override via env before running this script)
POOL_SIZE="${POOL_SIZE:-4}"
MAX_QUEUE_SIZE="${MAX_QUEUE_SIZE:-50}"
PAGE_TIMEOUT_MS="${PAGE_TIMEOUT_MS:-30000}"

# ─── Build ───────────────────────────────────────────────────────────────────
echo "==> Building image: ${IMAGE_NAME}"
docker build -t "${IMAGE_NAME}" .

# ─── Stop & remove old container (if any) ────────────────────────────────────
echo "==> Stopping old container (if running)..."
docker stop "${CONTAINER_NAME}" 2>/dev/null || true
docker rm   "${CONTAINER_NAME}" 2>/dev/null || true

# ─── Run ─────────────────────────────────────────────────────────────────────
echo "==> Starting container: ${CONTAINER_NAME}"
docker run -d \
  --name "${CONTAINER_NAME}" \
  -p "${HOST_PORT}:3000" \
  --restart unless-stopped \
  -e POOL_SIZE="${POOL_SIZE}" \
  -e MAX_QUEUE_SIZE="${MAX_QUEUE_SIZE}" \
  -e PAGE_TIMEOUT_MS="${PAGE_TIMEOUT_MS}" \
  "${IMAGE_NAME}"

# ─── Health check ─────────────────────────────────────────────────────────────
echo "==> Waiting for server to be ready..."
for i in $(seq 1 20); do
  if curl -sf "http://localhost:${HOST_PORT}/health" > /dev/null 2>&1; then
    echo "==> Server is healthy!"
    curl -s "http://localhost:${HOST_PORT}/health"
    echo ""
    break
  fi
  echo "   Attempt ${i}/20 — not ready yet, retrying in 2s..."
  sleep 2
done

echo ""
echo "==> Deploy complete."
echo "    Container : ${CONTAINER_NAME}"
echo "    Port      : ${HOST_PORT}"
echo "    Pool size : ${POOL_SIZE} browsers"
echo "    Max queue : ${MAX_QUEUE_SIZE} requests"
echo "    Timeout   : ${PAGE_TIMEOUT_MS} ms"
echo ""
echo "    Health    : http://localhost:${HOST_PORT}/health"
echo "    Render    : POST http://localhost:${HOST_PORT}/render"
