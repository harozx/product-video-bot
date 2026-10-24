"""
Cloudflare R2 storage client.
S3-compatible API for storing videos, images, and thumbnails.
"""

import logging
import mimetypes
from pathlib import Path
from typing import Optional

import boto3
from botocore.config import Config as BotoConfig

from config import R2Config

logger = logging.getLogger(__name__)

_s3_client = None


def get_r2_client():
    """Get or create the R2 S3 client (singleton)."""
    global _s3_client

    if _s3_client is not None:
        return _s3_client

    if not R2Config.ACCESS_KEY or R2Config.ACCESS_KEY == "your_r2_access_key":
        logger.warning("⚠️ R2 credentials not set — cloud storage disabled")
        return None

    if not R2Config.ACCOUNT_ID or R2Config.ACCOUNT_ID == "your_cf_account_id":
        logger.warning("⚠️ R2 account ID not set — cloud storage disabled")
        return None

    try:
        _s3_client = boto3.client(
            "s3",
            endpoint_url=R2Config.ENDPOINT,
            aws_access_key_id=R2Config.ACCESS_KEY,
            aws_secret_access_key=R2Config.SECRET_KEY,
            config=BotoConfig(
                region_name="auto",
                retries={"max_attempts": 3, "mode": "adaptive"},
            ),
        )
        logger.info(f"✅ R2 client initialized — bucket: {R2Config.BUCKET}")
        return _s3_client
    except Exception as e:
        logger.warning(f"⚠️ R2 client failed to initialize: {e}")
        return None


def upload_file(
    local_path: str,
    r2_key: str = "",
    content_type: str = "",
) -> Optional[str]:
    """
    Upload a file to R2.

    Args:
        local_path: Path to local file.
        r2_key: R2 object key (default: auto-generated from filename).
        content_type: MIME type (default: auto-detected).

    Returns:
        Public URL of the uploaded file, or None on failure.
    """
    client = get_r2_client()
    if not client:
        return None

    path = Path(local_path)
    if not path.exists():
        logger.error(f"❌ File not found: {local_path}")
        return None

    if not r2_key:
        r2_key = f"videos/{path.name}"

    if not content_type:
        content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"

    try:
        client.upload_file(
            str(path),
            R2Config.BUCKET,
            r2_key,
            ExtraArgs={"ContentType": content_type},
        )

        url = f"{R2Config.PUBLIC_URL}/{r2_key}" if R2Config.PUBLIC_URL else r2_key
        logger.info(f"✅ Uploaded to R2: {r2_key} ({path.stat().st_size / 1024:.0f}KB)")
        return url

    except Exception as e:
        logger.error(f"❌ R2 upload failed: {e}")
        return None


def delete_file(r2_key: str) -> bool:
    """Delete a file from R2."""
    client = get_r2_client()
    if not client:
        return False

    try:
        client.delete_object(Bucket=R2Config.BUCKET, Key=r2_key)
        logger.info(f"🗑️ Deleted from R2: {r2_key}")
        return True
    except Exception as e:
        logger.error(f"❌ R2 delete failed: {e}")
        return False


def list_files(prefix: str = "", max_keys: int = 1000) -> list[dict]:
    """List files in R2 bucket with optional prefix filter."""
    client = get_r2_client()
    if not client:
        return []

    try:
        response = client.list_objects_v2(
            Bucket=R2Config.BUCKET,
            Prefix=prefix,
            MaxKeys=max_keys,
        )
        files = []
        for obj in response.get("Contents", []):
            files.append({
                "key": obj["Key"],
                "size": obj["Size"],
                "last_modified": obj["LastModified"].isoformat(),
            })
        return files
    except Exception as e:
        logger.error(f"❌ R2 list failed: {e}")
        return []


def get_storage_usage() -> dict:
    """Get total storage usage in R2."""
    files = list_files(max_keys=10000)
    total_bytes = sum(f["size"] for f in files)
    return {
        "total_files": len(files),
        "total_bytes": total_bytes,
        "total_mb": round(total_bytes / (1024 * 1024), 2),
        "total_gb": round(total_bytes / (1024 * 1024 * 1024), 3),
    }
