#!/usr/bin/env bash
set -euo pipefail

export PYTHONUNBUFFERED=1
export PORT="${PORT:-7860}"

# Always use /tmp for Qdrant on HF Spaces
export QDRANT_PATH="/tmp/qdrant"
export S3_BUCKET="${S3_BUCKET_NAME:-}"
export S3_DB_KEY="${S3_DB_KEY:-qdrant_database.tar.gz}"

# CRITICAL: Set Chainlit to use /tmp as its app root
export CHAINLIT_APP_ROOT="/tmp"

echo "[startup] 🚀 Running on Hugging Face Spaces"
echo "[startup] PORT=$PORT  QDRANT_PATH=$QDRANT_PATH"
echo "[startup] S3_BUCKET=$S3_BUCKET"
echo "[startup] CHAINLIT_APP_ROOT=$CHAINLIT_APP_ROOT"

# Create qdrant directory (Chainlit will create its own dirs in /tmp)
mkdir -p "$QDRANT_PATH"

# Function to download database from S3
download_database_from_s3() {
  if [ -z "$S3_BUCKET" ]; then
    echo "[s3] ❌ S3_BUCKET_NAME not set"
    return 1
  fi

  echo "[s3] 📥 Downloading database from S3..."

  if python3 -c "
import boto3
import os
import tarfile
from botocore.exceptions import NoCredentialsError, ClientError

try:
    s3 = boto3.client('s3')
    bucket = os.environ['S3_BUCKET_NAME']
    key = os.environ['S3_DB_KEY']

    # Check if file exists
    s3.head_object(Bucket=bucket, Key=key)
    print('[s3] ✅ Found database in S3, downloading...')

    # Download and extract
    s3.download_file(bucket, key, '/tmp/qdrant_db.tar.gz')

    with tarfile.open('/tmp/qdrant_db.tar.gz', 'r:gz') as tar:
        tar.extractall('/tmp/')

    os.remove('/tmp/qdrant_db.tar.gz')
    print('[s3] ✅ Database downloaded and extracted successfully')

except ClientError as e:
    if e.response['Error']['Code'] == '404':
        print('[s3] 📭 No database found in S3')
        print('[s3] 💡 Run ingestion locally and upload with: python upload_to_s3.py')
        exit(1)
    else:
        print(f'[s3] ❌ S3 error: {e}')
        exit(1)
except NoCredentialsError:
    print('[s3] ❌ AWS credentials not found')
    exit(1)
except Exception as e:
    print(f'[s3] ❌ Error: {e}')
    exit(1)
  "; then
    return 0
  else
    return 1
  fi
}

# Download database from S3
if download_database_from_s3; then
  echo "[startup] ✅ Database loaded from S3"

  # Quick health check
  if [ -f "$QDRANT_PATH/collection/rag_chunks/storage.sqlite" ] && [ -s "$QDRANT_PATH/collection/rag_chunks/storage.sqlite" ]; then
    echo "[startup] 📊 Database looks healthy"
  else
    echo "[startup] ⚠️  Database downloaded but may be corrupted"
  fi
else
  echo ""
  echo "❌ NO DATABASE AVAILABLE"
  echo ""
  echo "To create and upload a database:"
  echo "1. Run locally: python -m ingest.ingest --config config/config.yaml"
  echo "2. Upload to S3: python upload_to_s3.py"
  echo "3. Restart this Space"
  echo ""
  exit 1
fi

echo ""
echo "[app] 🚀 Launching Chainlit on port $PORT..."
echo "[app] 🌐 Your RAG chatbot will be available shortly!"

exec chainlit run app/main.py --host 0.0.0.0 --port "$PORT"