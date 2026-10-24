"""
Auto cleanup worker.
Manages storage lifecycle: local → R2 → archive/delete.
Runs daily at configured hour (default 3AM).
"""

import asyncio
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

from config import TEMP_DIR, LOCAL_RETENTION_DAYS, R2_RETENTION_DAYS
from database import execute_query, execute_insert, execute_update, vacuum_database
from storage.r2_client import delete_file, list_files

logger = logging.getLogger(__name__)


async def run_cleanup() -> dict:
    """
    Run full cleanup cycle.
    Returns summary of actions taken.
    """
    logger.info("🧹 Starting cleanup cycle...")
    summary = {
        "temp_deleted": 0,
        "local_videos_deleted": 0,
        "r2_videos_deleted": 0,
        "bytes_freed": 0,
    }

    # 1. Clean temp directory (>24h old)
    temp_result = await _clean_temp_files()
    summary["temp_deleted"] = temp_result["files"]
    summary["bytes_freed"] += temp_result["bytes"]

    # 2. Clean local videos older than retention period
    local_result = await _clean_local_videos()
    summary["local_videos_deleted"] = local_result["files"]
    summary["bytes_freed"] += local_result["bytes"]

    # 3. Clean R2 videos older than retention period
    r2_result = await _clean_r2_videos()
    summary["r2_videos_deleted"] = r2_result["files"]

    # 4. Vacuum database weekly (on Sundays)
    if datetime.now().weekday() == 6:
        await vacuum_database()

    # Log cleanup
    await execute_insert(
        """INSERT INTO cleanup_log (action, files_deleted, bytes_freed, details)
           VALUES (?, ?, ?, ?)""",
        (
            "scheduled_cleanup",
            summary["temp_deleted"] + summary["local_videos_deleted"] + summary["r2_videos_deleted"],
            summary["bytes_freed"],
            str(summary),
        ),
    )

    logger.info(
        f"✅ Cleanup complete — "
        f"temp: {summary['temp_deleted']}, "
        f"local: {summary['local_videos_deleted']}, "
        f"R2: {summary['r2_videos_deleted']}, "
        f"freed: {summary['bytes_freed'] / (1024*1024):.1f}MB"
    )
    return summary


async def _clean_temp_files() -> dict:
    """Delete temp files older than 24 hours."""
    cutoff = time.time() - 86400  # 24h
    files_deleted = 0
    bytes_freed = 0

    if not TEMP_DIR.exists():
        return {"files": 0, "bytes": 0}

    for f in TEMP_DIR.iterdir():
        if f.is_file() and f.stat().st_mtime < cutoff:
            try:
                size = f.stat().st_size
                f.unlink()
                files_deleted += 1
                bytes_freed += size
            except Exception as e:
                logger.warning(f"⚠️ Failed to delete temp file {f}: {e}")

    if files_deleted:
        logger.info(f"🗑️ Temp cleanup: {files_deleted} files, {bytes_freed / 1024:.0f}KB freed")

    return {"files": files_deleted, "bytes": bytes_freed}


async def _clean_local_videos() -> dict:
    """
    Delete local video files that:
    - Are older than LOCAL_RETENTION_DAYS
    - Have already been uploaded to R2
    """
    cutoff_date = (datetime.now() - timedelta(days=LOCAL_RETENTION_DAYS)).isoformat()
    files_deleted = 0
    bytes_freed = 0

    # Find videos that are uploaded to R2 and old enough
    old_videos = await execute_query(
        """SELECT id, file_path FROM videos
           WHERE r2_key IS NOT NULL
             AND r2_key != ''
             AND file_path IS NOT NULL
             AND file_path != ''
             AND created_at < ?""",
        (cutoff_date,),
    )

    for video in old_videos:
        file_path = Path(video["file_path"])
        if file_path.exists():
            try:
                size = file_path.stat().st_size
                file_path.unlink()
                files_deleted += 1
                bytes_freed += size

                # Update DB — clear local path
                await execute_update(
                    "UPDATE videos SET file_path = NULL WHERE id = ?",
                    (video["id"],),
                )
            except Exception as e:
                logger.warning(f"⚠️ Failed to delete local video {file_path}: {e}")

    if files_deleted:
        logger.info(f"🗑️ Local cleanup: {files_deleted} videos, {bytes_freed / (1024*1024):.1f}MB freed")

    return {"files": files_deleted, "bytes": bytes_freed}


async def _clean_r2_videos() -> dict:
    """
    Delete R2 videos older than R2_RETENTION_DAYS.
    Keep metadata and thumbnail in database.
    """
    cutoff_date = (datetime.now() - timedelta(days=R2_RETENTION_DAYS)).isoformat()
    files_deleted = 0

    # Find old videos with R2 keys
    old_videos = await execute_query(
        """SELECT id, r2_key FROM videos
           WHERE r2_key IS NOT NULL
             AND r2_key != ''
             AND created_at < ?""",
        (cutoff_date,),
    )

    for video in old_videos:
        if delete_file(video["r2_key"]):
            files_deleted += 1
            await execute_update(
                "UPDATE videos SET r2_key = NULL, r2_url = NULL WHERE id = ?",
                (video["id"],),
            )

    if files_deleted:
        logger.info(f"🗑️ R2 cleanup: {files_deleted} videos deleted from cloud")

    return {"files": files_deleted, "bytes": 0}


async def get_storage_stats() -> dict:
    """Get current storage usage stats."""
    # Local temp
    temp_size = sum(f.stat().st_size for f in TEMP_DIR.iterdir() if f.is_file()) if TEMP_DIR.exists() else 0

    # Count videos
    video_counts = await execute_query(
        """SELECT
               COUNT(*) as total,
               COUNT(file_path) as local_count,
               COUNT(r2_key) as r2_count,
               SUM(CASE WHEN file_path IS NOT NULL THEN 1 ELSE 0 END) as with_local
           FROM videos"""
    )

    stats = video_counts[0] if video_counts else {}

    return {
        "temp_size_mb": round(temp_size / (1024 * 1024), 2),
        "total_videos": stats.get("total", 0),
        "local_videos": stats.get("with_local", 0),
        "r2_videos": stats.get("r2_count", 0),
    }
