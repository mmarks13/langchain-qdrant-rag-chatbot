#!/usr/bin/env bash
set -euo pipefail

export PYTHONUNBUFFERED=1
export PORT="${PORT:-7860}"

# Use Hugging Face Spaces persistent storage if available
if [ "${SPACE_ID:-}" != "" ]; then
  echo "[startup] 🚀 Running on Hugging Face Spaces"
  export QDRANT_PATH="/data/qdrant"
else
  export QDRANT_PATH="${QDRANT_PATH:-./data/qdrant}"
fi

echo "[startup] PORT=$PORT  QDRANT_PATH=$QDRANT_PATH"
mkdir -p "$QDRANT_PATH"

# Simple control: RUN_INGESTION environment variable
# Set to "true" in HF Spaces to run ingestion, "false" to skip
if [ "${RUN_INGESTION:-false}" = "true" ]; then
  echo "[startup] 🔧 RUN_INGESTION=true - running ingestion (THIS COSTS MONEY!)"
  NEEDS_INGEST=true
else
  echo "[startup] ⏭️  RUN_INGESTION=${RUN_INGESTION:-false} - skipping ingestion"
  NEEDS_INGEST=false
fi

if [ "$NEEDS_INGEST" = "true" ]; then
  echo ""
  echo "💸 RUNNING COSTLY INGESTION..."
  echo "   This will charge your Firecrawl account"
  echo "   Database will be saved to persistent storage"
  echo ""

  python -m ingest.ingest --config config/config.yaml || {
    echo "[ERROR] Ingestion failed!"
  }

  echo "[ingest] ✅ Ingestion completed - saved to persistent storage"
  echo "[ingest] 💡 Set RUN_INGESTION=false to avoid running again"
else
  echo "[startup] ✅ Skipping ingestion - using existing data"
fi

echo ""
echo "[app] 🚀 Launching Chainlit..."
exec chainlit run app/main.py --host 0.0.0.0 --port "$PORT"