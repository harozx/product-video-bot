"""
Videos API router.
CRUD operations and video management.
"""

import json
from fastapi import APIRouter, HTTPException, Query

from database import execute_query, execute_update
from server.models.schemas import VideoResponse

router = APIRouter(prefix="/api/videos", tags=["Videos"])


@router.get("", response_model=list[VideoResponse])
async def list_videos(
    status: str = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List all videos with optional status filter."""
    if status:
        videos = await execute_query(
            "SELECT * FROM videos WHERE status = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (status, limit, offset),
        )
    else:
        videos = await execute_query(
            "SELECT * FROM videos ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )

    for v in videos:
        v["hashtags"] = json.loads(v.get("hashtags") or "[]")
    return videos


@router.get("/{video_id}", response_model=VideoResponse)
async def get_video(video_id: int):
    """Get a single video by ID."""
    videos = await execute_query("SELECT * FROM videos WHERE id = ?", (video_id,))
    if not videos:
        raise HTTPException(404, "Video not found")
    videos[0]["hashtags"] = json.loads(videos[0].get("hashtags") or "[]")
    return videos[0]


@router.patch("/{video_id}/status")
async def update_video_status(video_id: int, status: str):
    """Update video status."""
    valid = ("rendering", "ready", "approved", "posted", "failed")
    if status not in valid:
        raise HTTPException(400, f"Invalid status. Must be one of: {valid}")
    rows = await execute_update(
        "UPDATE videos SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (status, video_id),
    )
    if rows == 0:
        raise HTTPException(404, "Video not found")
    return {"message": f"Video #{video_id} status updated to '{status}'"}


@router.delete("/{video_id}")
async def delete_video(video_id: int):
    """Delete a video."""
    rows = await execute_update("DELETE FROM videos WHERE id = ?", (video_id,))
    if rows == 0:
        raise HTTPException(404, "Video not found")
    return {"message": f"Video #{video_id} deleted"}
