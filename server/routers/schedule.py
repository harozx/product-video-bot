"""
Schedule API router.
Manage content posting schedule.
"""

from fastapi import APIRouter, HTTPException, Query

from database import execute_query, execute_insert, execute_update
from server.models.schemas import ScheduleCreate, ScheduleResponse

router = APIRouter(prefix="/api/schedule", tags=["Schedule"])


@router.get("", response_model=list[ScheduleResponse])
async def list_schedule(
    status: str = Query(None),
    platform: str = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """List scheduled posts."""
    conditions = []
    params = []

    if status:
        conditions.append("s.status = ?")
        params.append(status)
    if platform:
        conditions.append("s.platform = ?")
        params.append(platform)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.extend([limit])

    return await execute_query(
        f"""SELECT s.* FROM schedule s {where}
            ORDER BY s.scheduled_at ASC LIMIT ?""",
        tuple(params),
    )


@router.post("", response_model=ScheduleResponse, status_code=201)
async def create_schedule(entry: ScheduleCreate):
    """Create a new scheduled post."""
    entry_id = await execute_insert(
        """INSERT INTO schedule (video_id, account_id, platform, scheduled_at, caption, hashtags)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (entry.video_id, entry.account_id, entry.platform,
         entry.scheduled_at, entry.caption, entry.hashtags),
    )
    entries = await execute_query("SELECT * FROM schedule WHERE id = ?", (entry_id,))
    return entries[0]


@router.patch("/{schedule_id}/cancel")
async def cancel_schedule(schedule_id: int):
    """Cancel a pending scheduled post."""
    rows = await execute_update(
        "UPDATE schedule SET status = 'cancelled' WHERE id = ? AND status = 'pending'",
        (schedule_id,),
    )
    if rows == 0:
        raise HTTPException(404, "Schedule not found or not pending")
    return {"message": f"Schedule #{schedule_id} cancelled"}


@router.get("/upcoming")
async def upcoming_posts(limit: int = Query(10, ge=1, le=50)):
    """Get upcoming posts with video and account info."""
    return await execute_query(
        """SELECT s.*, v.caption_tiktok, v.r2_url, a.account_name, a.platform as acc_platform
           FROM schedule s
           JOIN videos v ON s.video_id = v.id
           JOIN accounts a ON s.account_id = a.id
           WHERE s.status = 'pending'
           ORDER BY s.scheduled_at ASC
           LIMIT ?""",
        (limit,),
    )
