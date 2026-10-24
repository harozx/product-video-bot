"""
Auto Content Pipeline — Main Entry Point.
Runs Telegram Bot + FastAPI server + Scheduler concurrently.
"""

import asyncio
import logging
import sys
import threading

import uvicorn
from apscheduler.schedulers.background import BackgroundScheduler
from telegram import Update
from telegram.error import NetworkError
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from ai.client import init_gemini
from bot.commands import (
    help_handler, status_handler, stats_handler,
    accounts_handler, add_account_handler,
    schedule_handler, cleanup_handler,
)
from bot.handlers import build_conversation_handler
from config import TelegramConfig, API_HOST, API_PORT, CLEANUP_HOUR
from database import init_database
from storage.cleanup import run_cleanup

# ── Logging ────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(name)-20s │ %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("auto_content.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("auto-content")

# Silence noisy loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)


def run_fastapi():
    """Run FastAPI in a background thread."""
    from server.main import app
    uvicorn.run(app, host=API_HOST, port=API_PORT, log_level="warning")


def run_cleanup_sync():
    """Sync wrapper for cleanup job."""
    asyncio.run(run_cleanup())


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Log bot errors; short network drops are retried by polling, so keep them to one line."""
    if isinstance(context.error, NetworkError):
        logger.warning(f"⚠️ Telegram network error (will retry): {context.error}")
        return
    logger.error("❌ Unhandled bot error", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text("❌ Có lỗi xảy ra, thử lại sau hoặc /start.")


def main():
    """Main entry point."""
    logger.info("=" * 55)
    logger.info("  🚀 Auto Content Pipeline — Starting...")
    logger.info("=" * 55)

    # 1. Initialize database (sync)
    asyncio.run(init_database())
    logger.info("✅ Database ready")

    # 2. Initialize Gemini
    try:
        init_gemini()
    except Exception as e:
        logger.warning(f"⚠️ Gemini init failed: {e}")

    # 3. Start FastAPI in background thread
    api_thread = threading.Thread(target=run_fastapi, daemon=True)
    api_thread.start()
    logger.info(f"✅ FastAPI running at http://{API_HOST}:{API_PORT}")
    logger.info(f"📖 API docs at http://{API_HOST}:{API_PORT}/docs")

    # 4. Setup scheduler (background, non-async)
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        run_cleanup_sync,
        trigger="cron",
        hour=CLEANUP_HOUR,
        minute=0,
        id="daily_cleanup",
    )
    scheduler.start()
    logger.info(f"✅ Scheduler running — cleanup at {CLEANUP_HOUR}:00")

    # 5. Start Telegram Bot (this manages its own event loop)
    if not TelegramConfig.BOT_TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN not set!")
        return

    app = (
        ApplicationBuilder()
        .token(TelegramConfig.BOT_TOKEN)
        .build()
    )

    # Register handlers
    app.add_handler(build_conversation_handler())
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("status", status_handler))
    app.add_handler(CommandHandler("stats", stats_handler))
    app.add_handler(CommandHandler("accounts", accounts_handler))
    app.add_handler(CommandHandler("add_account", add_account_handler))
    app.add_handler(CommandHandler("schedule", schedule_handler))
    app.add_handler(CommandHandler("cleanup", cleanup_handler))
    app.add_error_handler(error_handler)

    logger.info("✅ Telegram Bot started!")
    logger.info("")
    logger.info("╔═══════════════════════════════════════╗")
    logger.info("║  🤖 All systems operational!          ║")
    logger.info("║  📸 Send product photos to the bot    ║")
    logger.info("║  🌐 Dashboard: http://localhost:8000  ║")
    logger.info("╚═══════════════════════════════════════╝")

    # run_polling manages its own event loop — need a fresh one
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
