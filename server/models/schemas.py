"""
Pydantic schemas for API request/response validation.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ── Products ───────────────────────────────────────────
class ProductCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    price: str = ""
    features: str = ""
    category: str = ""
    niche: str = "general"


class ProductResponse(BaseModel):
    id: int
    name: str
    price: str | None
    features: str | None
    category: str | None
    niche: str | None
    created_at: str


# ── Videos ─────────────────────────────────────────────
class VideoResponse(BaseModel):
    id: int
    product_id: int
    template: str | None
    veo_tier: str | None
    duration_seconds: float | None
    r2_url: str | None
    caption_tiktok: str | None
    caption_facebook: str | None
    hashtags: list[str] = []
    status: str
    render_cost: float
    created_at: str


# ── Accounts ───────────────────────────────────────────
class AccountCreate(BaseModel):
    platform: str = Field(..., pattern=r"^(tiktok|facebook)$")
    account_name: str = Field(..., min_length=1)
    username: str = ""
    page_id: str = ""
    niche: str = "general"
    daily_post_limit: int = 3


class AccountResponse(BaseModel):
    id: int
    platform: str
    account_name: str
    username: str | None
    page_id: str | None
    niche: str | None
    status: str
    daily_post_limit: int
    posts_today: int
    last_posted_at: str | None
    created_at: str


# ── Schedule ───────────────────────────────────────────
class ScheduleCreate(BaseModel):
    video_id: int
    account_id: int
    platform: str = Field(..., pattern=r"^(tiktok|facebook)$")
    scheduled_at: str
    caption: str = ""
    hashtags: str = ""


class ScheduleResponse(BaseModel):
    id: int
    video_id: int
    account_id: int
    platform: str
    caption: str | None
    scheduled_at: str
    posted_at: str | None
    post_url: str | None
    status: str
    retry_count: int


# ── System ─────────────────────────────────────────────
class SystemStats(BaseModel):
    total_videos: int
    total_posted: int
    total_cost: float
    active_accounts: int
    pending_posts: int
    storage_mb: float


class HealthResponse(BaseModel):
    status: str = "ok"
    uptime: str
    version: str = "1.0.0"
    services: dict = {}
