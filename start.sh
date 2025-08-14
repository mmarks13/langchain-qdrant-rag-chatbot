#!/usr/bin/env bash
set -euo pipefail

export PYTHONUNBUFFERED=1
export PORT="${PORT:-7860}"
export QDRANT_PATH="${QDRANT_PATH:-/data/qdrant}"

echo "[startup] PORT=$PORT  QDRANT_PATH=$QDRANT_PATH"
mkdir -p "$QDRANT_PATH"

# Run ingestion once (or if forced)
NEEDS_INGEST=false
if [ "${QDRANT_RESET:-}" = "true" ] || [ "${QDRANT_RESET:-}" = "1" ]; then
  echo "[startup] QDRANT_RESET requested."
  NEEDS_INGEST=true
elif [ -z "$(ls -A "$QDRANT_PATH" 2>/dev/null)" ]; then
  echo "[startup] Qdrant path is empty; will run initial ingestion."
  NEEDS_INGEST=true
fi

if [ "$NEEDS_INGEST" = "true" ]; then
  echo "[ingest] Starting ingestion..."
  python -m ingest.ingest --config config/config.yaml ${QDRANT_RESET:+--reset} || {
    echo "[ingest] Warning: ingestion exited non-zero; continuing to app."
  }
fi

echo "[app] Launching Chainlit…"
exec chainlit run app/main.py --host 0.0.0.0 --port "$PORT"
