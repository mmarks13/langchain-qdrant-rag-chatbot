#!/usr/bin/env python3
"""
Upload your local Qdrant database to S3 for use in Hugging Face Spaces.

Usage:
    python upload_to_s3.py [--config config/config.yaml] [--force]

Environment variables required:
    AWS_ACCESS_KEY_ID
    AWS_SECRET_ACCESS_KEY
    AWS_DEFAULT_REGION (optional, defaults to us-east-1)
    S3_BUCKET_NAME
    S3_DB_KEY (optional, defaults to qdrant_database.tar.gz)
"""

import os
import sys
import argparse
import tarfile
import boto3
from datetime import datetime
from pathlib import Path
from botocore.exceptions import NoCredentialsError, ClientError
from dotenv import load_dotenv

def load_config_for_path(config_path: str) -> str:
    """Get the Qdrant path from config."""
    try:
        from app.config_utils import load_config
        cfg = load_config(config_path)
        return cfg["vectorstore"]["path"]
    except Exception as e:
        print(f"❌ Could not load config: {e}")
        return "data/qdrant"  # fallback

def check_database(qdrant_path: str) -> bool:
    """Check if database exists and is valid."""
    db_file = Path(qdrant_path) / "collection" / "rag_chunks" / "storage.sqlite"

    if not db_file.exists():
        print(f"❌ Database not found at: {db_file}")
        print("   Run: python -m ingest.ingest --config config/config.yaml")
        return False

    if db_file.stat().st_size == 0:
        print(f"❌ Database file is empty: {db_file}")
        return False

    print(f"✅ Database found: {db_file}")
    print(f"   Size: {db_file.stat().st_size / (1024*1024):.1f} MB")

    # Quick health check with Qdrant
    try:
        from qdrant_client import QdrantClient
        client = QdrantClient(path=qdrant_path)
        info = client.get_collection('rag_chunks')
        print(f"   Documents: {info.points_count}")
        return True
    except Exception as e:
        print(f"⚠️  Database health check failed: {e}")
        print("   Continuing anyway...")
        return True  # Continue even if health check fails

def upload_to_s3(qdrant_path: str, bucket: str, key: str, force: bool = False) -> bool:
    """Upload database to S3."""

    # Check if file already exists
    try:
        s3 = boto3.client('s3')
        s3.head_object(Bucket=bucket, Key=key)

        if not force:
            print(f"⚠️  Database already exists in S3: s3://{bucket}/{key}")
            response = input("Overwrite? [y/N]: ").lower().strip()
            if response != 'y' and response != 'yes':
                print("❌ Upload cancelled")
                return False
    except ClientError as e:
        if e.response['Error']['Code'] != '404':
            print(f"❌ S3 error checking existing file: {e}")
            return False
        # File doesn't exist, which is fine

    # Create compressed archive
    print("📦 Compressing database...")
    archive_path = "/tmp/qdrant_db.tar.gz"

    try:
        with tarfile.open(archive_path, 'w:gz') as tar:
            tar.add(qdrant_path, arcname='qdrant')

        archive_size = Path(archive_path).stat().st_size / (1024*1024)
        print(f"   Compressed size: {archive_size:.1f} MB")

    except Exception as e:
        print(f"❌ Compression failed: {e}")
        return False

    # Upload to S3
    print(f"📤 Uploading to s3://{bucket}/{key}...")

    try:
        s3.upload_file(archive_path, bucket, key)
        print(f"✅ Database uploaded successfully!")

        # Create timestamped backup
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_key = f"backups/qdrant_database_{timestamp}.tar.gz"
        s3.upload_file(archive_path, bucket, backup_key)
        print(f"💾 Backup saved: s3://{bucket}/{backup_key}")

        # Clean up
        os.remove(archive_path)

        print("")
        print("🎉 SUCCESS!")
        print("   Your Hugging Face Space can now download this database")
        print("   The Space will automatically use this data on startup")

        return True

    except NoCredentialsError:
        print("❌ AWS credentials not found")
        print("   Set: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY")
        return False
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Upload Qdrant database to S3")
    parser.add_argument("--config", default="config/config.yaml", help="Config file path")
    parser.add_argument("--force", action="store_true", help="Overwrite existing S3 file")
    parser.add_argument("--qdrant-path", help="Override Qdrant path from config")

    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    # Check required environment variables
    bucket = os.getenv("S3_BUCKET_NAME")
    if not bucket:
        print("❌ S3_BUCKET_NAME environment variable not set")
        sys.exit(1)

    key = os.getenv("S3_DB_KEY", "qdrant_database.tar.gz")

    # AWS credentials check
    if not os.getenv("AWS_ACCESS_KEY_ID") or not os.getenv("AWS_SECRET_ACCESS_KEY"):
        print("❌ AWS credentials not found")
        print("   Set: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY")
        sys.exit(1)

    # Get Qdrant path
    if args.qdrant_path:
        qdrant_path = args.qdrant_path
    else:
        qdrant_path = load_config_for_path(args.config)

    print(f"🔍 Checking database at: {qdrant_path}")

    # Check database
    if not check_database(qdrant_path):
        sys.exit(1)

    # Upload to S3
    print(f"☁️  S3 Target: s3://{bucket}/{key}")

    if upload_to_s3(qdrant_path, bucket, key, args.force):
        print("\n💡 Next steps:")
        print("   1. Your Hugging Face Space will now use this database")
        print("   2. No need to run ingestion on the Space anymore")
        print("   3. To update data: re-run ingestion locally and upload again")
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()