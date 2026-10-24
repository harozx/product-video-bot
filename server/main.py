"""
FastAPI server — Dashboard API backend.
Provides REST endpoints for the Vue dashboard.
"""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_database, execute_query
from storage.cleanup import get_storage_stats
from server.routers import videos, accounts, schedule

logger = logging.getLogger(__name__)
_start_time = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown."""
    # Startup
    await init_database()
    logger.info("⚡ FastAPI server started")
    yield
    # Shutdown
    logger.info("👋 FastAPI server stopped")


app = FastAPI(
    title="Auto Content Pipeline",
    description="API for managing automated video content creation and social media posting",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow dashboard access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(videos.router)
app.include_router(accounts.router)
app.include_router(schedule.router)


@app.get("/api/health")
async def health():
    """System health check."""
    uptime_seconds = int(time.time() - _start_time)
    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    return {
        "status": "ok",
        "uptime": f"{hours}h {minutes}m {seconds}s",
        "version": "1.0.0",
    }


@app.get("/api/stats")
async def system_stats():
    """System statistics for dashboard."""
    total_videos = await execute_query("SELECT COUNT(*) as c FROM videos")
    total_posted = await execute_query(
        "SELECT COUNT(*) as c FROM schedule WHERE status='posted'"
    )
    total_cost = await execute_query(
        "SELECT COALESCE(SUM(render_cost),0) as c FROM videos"
    )
    active_accounts = await execute_query(
        "SELECT COUNT(*) as c FROM accounts WHERE status='active'"
    )
    pending = await execute_query(
        "SELECT COUNT(*) as c FROM schedule WHERE status='pending'"
    )
    storage = await get_storage_stats()

    return {
        "total_videos": total_videos[0]["c"],
        "total_posted": total_posted[0]["c"],
        "total_cost": round(total_cost[0]["c"], 2),
        "active_accounts": active_accounts[0]["c"],
        "pending_posts": pending[0]["c"],
        "storage_mb": storage.get("temp_size_mb", 0),
    }
