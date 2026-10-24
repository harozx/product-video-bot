"""
SQLite database setup and management.
All tables for products, media, videos, accounts, schedule, analytics.
"""

import aiosqlite
import logging
from pathlib import Path

from config import DATABASE_PATH

logger = logging.getLogger(__name__)

SCHEMA = """
-- ══════════════════════════════════════════
-- Products
-- ══════════════════════════════════════════
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    price TEXT,
    features TEXT,
    category TEXT,
    niche TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ══════════════════════════════════════════
-- Source media (images/videos from Telegram)
-- ══════════════════════════════════════════
CREATE TABLE IF NOT EXISTS media (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    file_path TEXT,
    r2_key TEXT,
    type TEXT NOT NULL DEFAULT 'image',  -- 'image' | 'video'
    telegram_file_id TEXT,
    width INTEGER,
    height INTEGER,
    size_bytes INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ══════════════════════════════════════════
-- Generated videos
-- ══════════════════════════════════════════
CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    template TEXT DEFAULT 'veo',         -- 'veo' | 'slideshow' | 'zoom_pan'
    veo_tier TEXT,                        -- 'lite' | 'fast' | 'standard'
    music_track TEXT,
    duration_seconds REAL,
    file_path TEXT,
    r2_key TEXT,
    r2_url TEXT,
    thumbnail_path TEXT,
    caption_tiktok TEXT,
    caption_facebook TEXT,
    hashtags TEXT,                        -- JSON array string
    status TEXT DEFAULT 'rendering',     -- rendering | ready | approved | posted | failed
    error_log TEXT,
    render_cost REAL DEFAULT 0,          -- USD cost of Veo generation
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ══════════════════════════════════════════
-- Social media accounts
-- ══════════════════════════════════════════
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,              -- 'tiktok' | 'facebook'
    account_name TEXT NOT NULL,
    username TEXT,
    page_id TEXT,                         -- Facebook Page ID
    access_token_enc TEXT,               -- Encrypted FB token
    cookies_path TEXT,
    proxy_id INTEGER REFERENCES proxies(id),
    browser_profile_id TEXT,
    niche TEXT,
    status TEXT DEFAULT 'active',        -- active | paused | banned | cooldown
    daily_post_limit INTEGER DEFAULT 3,
    posts_today INTEGER DEFAULT 0,
    last_posted_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ══════════════════════════════════════════
-- Proxy pool
-- ══════════════════════════════════════════
CREATE TABLE IF NOT EXISTS proxies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT DEFAULT 'iproyal',
    type TEXT DEFAULT 'residential',     -- residential | mobile | isp
    host TEXT NOT NULL,
    port INTEGER NOT NULL,
    username TEXT,
    password TEXT,
    country TEXT DEFAULT 'VN',
    assigned_account_id INTEGER,         -- 1:1 mapping
    is_healthy INTEGER DEFAULT 1,
    last_checked_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ══════════════════════════════════════════
-- Content schedule & posting log
-- ══════════════════════════════════════════
CREATE TABLE IF NOT EXISTS schedule (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    platform TEXT NOT NULL,              -- 'tiktok' | 'facebook'
    caption TEXT,
    hashtags TEXT,
    scheduled_at DATETIME NOT NULL,
    posted_at DATETIME,
    post_url TEXT,
    status TEXT DEFAULT 'pending',       -- pending | posting | posted | failed | cancelled
    retry_count INTEGER DEFAULT 0,
    error_log TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ══════════════════════════════════════════
-- Analytics (per post)
-- ══════════════════════════════════════════
CREATE TABLE IF NOT EXISTS analytics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    schedule_id INTEGER NOT NULL REFERENCES schedule(id) ON DELETE CASCADE,
    views INTEGER DEFAULT 0,
    likes INTEGER DEFAULT 0,
    comments INTEGER DEFAULT 0,
    shares INTEGER DEFAULT 0,
    followers_gained INTEGER DEFAULT 0,
    fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ══════════════════════════════════════════
-- System settings (KV store)
-- ══════════════════════════════════════════
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ══════════════════════════════════════════
-- Cleanup log
-- ══════════════════════════════════════════
CREATE TABLE IF NOT EXISTS cleanup_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,
    files_deleted INTEGER DEFAULT 0,
    bytes_freed INTEGER DEFAULT 0,
    details TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ══════════════════════════════════════════
-- Indexes
-- ══════════════════════════════════════════
CREATE INDEX IF NOT EXISTS idx_media_product ON media(product_id);
CREATE INDEX IF NOT EXISTS idx_videos_product ON videos(product_id);
CREATE INDEX IF NOT EXISTS idx_videos_status ON videos(status);
CREATE INDEX IF NOT EXISTS idx_schedule_status ON schedule(status);
CREATE INDEX IF NOT EXISTS idx_schedule_time ON schedule(scheduled_at);
CREATE INDEX IF NOT EXISTS idx_accounts_platform ON accounts(platform);
CREATE INDEX IF NOT EXISTS idx_accounts_status ON accounts(status);
"""


async def init_database() -> None:
    """Initialize database with schema."""
    db_path = Path(DATABASE_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.executescript(SCHEMA)
        await db.commit()
        logger.info(f"✅ Database initialized at {DATABASE_PATH}")


async def get_db() -> aiosqlite.Connection:
    """Get a database connection (use as context manager)."""
    db = await aiosqlite.connect(DATABASE_PATH)
    db.row_factory = aiosqlite.Row
    return db


async def execute_query(query: str, params: tuple = ()) -> list[dict]:
    """Execute a SELECT query and return results as dicts."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def execute_insert(query: str, params: tuple = ()) -> int:
    """Execute an INSERT query and return the last row ID."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(query, params) as cursor:
            await db.commit()
            return cursor.lastrowid


async def execute_update(query: str, params: tuple = ()) -> int:
    """Execute an UPDATE/DELETE query and return rows affected."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(query, params) as cursor:
            await db.commit()
            return cursor.rowcount


async def vacuum_database() -> None:
    """Reclaim unused space in the database file."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("VACUUM")
        logger.info("🧹 Database vacuumed")
