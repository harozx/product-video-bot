"""
Centralized configuration for Auto Content Pipeline.
Loads environment variables and provides typed access.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

__version__ = "1.0.0"

# ── Paths ──────────────────────────────────────────────
BASE_DIR = Path(__file__).parent

# ── Load .env ──────────────────────────────────────────
load_dotenv(BASE_DIR / ".env")

DATA_DIR = BASE_DIR / "data"
TEMP_DIR = Path(os.getenv("TEMP_DIR", str(DATA_DIR / "temp")))
MUSIC_DIR = Path(os.getenv("MUSIC_DIR", str(BASE_DIR / "music")))
PROFILES_DIR = Path(os.getenv("PROFILES_DIR", str(DATA_DIR / "profiles")))
CREDENTIALS_DIR = BASE_DIR / "credentials"

# Create directories
for d in [DATA_DIR, TEMP_DIR, MUSIC_DIR, PROFILES_DIR, CREDENTIALS_DIR,
          MUSIC_DIR / "trending", MUSIC_DIR / "chill", MUSIC_DIR / "energetic"]:
    d.mkdir(parents=True, exist_ok=True)


# ── Google AI ──────────────────────────────────────────
class GoogleConfig:
    API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    PROJECT_ID: str = os.getenv("GOOGLE_CLOUD_PROJECT", "")
    CREDENTIALS_PATH: str = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
    GCS_BUCKET: str = os.getenv("GCS_BUCKET", "auto-content-media")

    # Gemini
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    # Veo
    VEO_MODEL: str = os.getenv("VEO_MODEL", "veo-3.1-generate-001")
    VEO_TIER: str = os.getenv("VEO_DEFAULT_TIER", "lite")
    VEO_DURATION: str = os.getenv("VEO_DURATION", "6s")
    VEO_ASPECT_RATIO: str = os.getenv("VEO_ASPECT_RATIO", "9:16")


# ── Telegram ───────────────────────────────────────────
class TelegramConfig:
    BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    ADMIN_IDS: list[int] = [
        int(x.strip())
        for x in os.getenv("TELEGRAM_ADMIN_IDS", "").split(",")
        if x.strip().isdigit() and int(x.strip()) > 0
    ]


# ── Cloudflare R2 ─────────────────────────────────────
class R2Config:
    ACCOUNT_ID: str = os.getenv("CF_ACCOUNT_ID", "")
    ACCESS_KEY: str = os.getenv("CF_R2_ACCESS_KEY", "")
    SECRET_KEY: str = os.getenv("CF_R2_SECRET_KEY", "")
    BUCKET: str = os.getenv("CF_R2_BUCKET", "auto-content")
    PUBLIC_URL: str = os.getenv("CF_R2_PUBLIC_URL", "")
    ENDPOINT: str = f"https://{ACCOUNT_ID}.r2.cloudflarestorage.com"


# ── Facebook ───────────────────────────────────────────
class FacebookConfig:
    APP_ID: str = os.getenv("FB_APP_ID", "")
    APP_SECRET: str = os.getenv("FB_APP_SECRET", "")


# ── Proxy ──────────────────────────────────────────────
class ProxyConfig:
    PROVIDER: str = os.getenv("PROXY_PROVIDER", "iproyal")


# ── Database ───────────────────────────────────────────
DATABASE_PATH: str = os.getenv("DATABASE_PATH", str(DATA_DIR / "database.db"))

# ── Cleanup ────────────────────────────────────────────
LOCAL_RETENTION_DAYS: int = int(os.getenv("LOCAL_RETENTION_DAYS", "7"))
R2_RETENTION_DAYS: int = int(os.getenv("R2_RETENTION_DAYS", "90"))
CLEANUP_HOUR: int = int(os.getenv("CLEANUP_HOUR", "3"))

# ── Server ─────────────────────────────────────────────
# The API has no authentication: keep it on localhost unless it sits behind a proxy with auth
API_HOST: str = os.getenv("API_HOST", "127.0.0.1")
API_PORT: int = int(os.getenv("API_PORT", "8000"))
DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

# ── MoneyPrinterTurbo ──────────────────────────────────
TURBO_BASE_URL: str = os.getenv("TURBO_BASE_URL", "http://127.0.0.1:8080")

# ── Video ──────────────────────────────────────────────
VIDEO_WIDTH: int = 1080
VIDEO_HEIGHT: int = 1920
VIDEO_FPS: int = 30
DEFAULT_CLIP_DURATION: float = 3.0  # seconds per image in slideshow
TRANSITION_DURATION: float = 0.5

# ── Prompts ────────────────────────────────────────────
CAPTION_PROMPT = """Viết caption marketing cho sản phẩm sau.

Sản phẩm: {product_name}
Giá: {price}
Đặc điểm: {features}
Niche: {niche}

Quy tắc:
- Caption TikTok: ngắn, hook mạnh dòng đầu, có emoji, dưới 80 từ, kết bằng CTA
- Caption Facebook: dài hơn một chút, chuyên nghiệp hơn, dưới 120 từ
- Hashtags: 8-12 hashtags liên quan, tiếng Việt lẫn tiếng Anh
- Viết tiếng Việt tự nhiên, phong cách gen Z

Trả về ĐÚNG JSON format sau, không thêm gì khác:
{{"caption_tiktok": "nội dung", "caption_facebook": "nội dung", "hashtags": ["#tag1", "#tag2"]}}"""

VEO_PRODUCT_PROMPT = """Cinematic product showcase video.
Smooth {motion_type}, professional studio lighting,
clean {background} background, commercial photography style.
Product: {product_name}. High quality, 4K detail."""
