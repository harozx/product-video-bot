"""
Telegram Bot command handlers.
/status, /help, /add_account, /accounts, /stats, /cleanup
"""

import json
import logging
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

from bot.handlers import is_admin
from database import execute_query, execute_insert, execute_update
from storage.cleanup import run_cleanup, get_storage_stats

logger = logging.getLogger(__name__)


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show available commands."""
    if not is_admin(update.effective_user.id):
        return

    await update.message.reply_text(
        "📖 **Danh sách lệnh:**\n\n"
        "📸 *Gửi ảnh* — Bắt đầu tạo video\n"
        "/start — Khởi động lại bot\n"
        "/status — Trạng thái hệ thống\n"
        "/stats — Thống kê\n"
        "/accounts — Danh sách tài khoản\n"
        "/add\\_account — Thêm tài khoản mới\n"
        "/schedule — Lịch đăng sắp tới\n"
        "/cleanup — Chạy dọn dẹp\n"
        "/cancel — Hủy thao tác hiện tại",
        parse_mode="Markdown",
    )


async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show system status."""
    if not is_admin(update.effective_user.id):
        return

    storage = await get_storage_stats()
    pending = await execute_query(
        "SELECT COUNT(*) as count FROM schedule WHERE status = 'pending'"
    )
    today_posted = await execute_query(
        "SELECT COUNT(*) as count FROM schedule WHERE status = 'posted' AND DATE(posted_at) = DATE('now')"
    )
    accounts = await execute_query(
        "SELECT platform, COUNT(*) as count FROM accounts WHERE status = 'active' GROUP BY platform"
    )

    acc_str = "\n".join(f"  • {a['platform']}: {a['count']}" for a in accounts) or "  Chưa có"

    await update.message.reply_text(
        "📊 **System Status**\n\n"
        f"💾 Storage:\n"
        f"  • Temp: {storage['temp_size_mb']}MB\n"
        f"  • Videos (local): {storage['local_videos']}\n"
        f"  • Videos (R2): {storage['r2_videos']}\n\n"
        f"📤 Hôm nay: {today_posted[0]['count']} đã đăng\n"
        f"⏳ Đang chờ: {pending[0]['count']} bài\n\n"
        f"👤 Accounts:\n{acc_str}",
        parse_mode="Markdown",
    )


async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show usage statistics."""
    if not is_admin(update.effective_user.id):
        return

    total_videos = await execute_query("SELECT COUNT(*) as c FROM videos")
    total_posted = await execute_query("SELECT COUNT(*) as c FROM schedule WHERE status='posted'")
    total_cost = await execute_query("SELECT COALESCE(SUM(render_cost),0) as c FROM videos")

    await update.message.reply_text(
        "📈 **Thống kê tổng quan**\n\n"
        f"🎬 Video đã tạo: {total_videos[0]['c']}\n"
        f"📤 Bài đã đăng: {total_posted[0]['c']}\n"
        f"💰 Chi phí Veo: ${total_cost[0]['c']:.2f}",
        parse_mode="Markdown",
    )


async def accounts_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all social media accounts."""
    if not is_admin(update.effective_user.id):
        return

    accounts = await execute_query("SELECT * FROM accounts ORDER BY platform, account_name")

    if not accounts:
        await update.message.reply_text("⚠️ Chưa có tài khoản nào. Dùng /add_account")
        return

    lines = ["👤 **Danh sách tài khoản:**\n"]
    for acc in accounts:
        icon = "🎵" if acc["platform"] == "tiktok" else "📘"
        status = "🟢" if acc["status"] == "active" else "🔴"
        lines.append(f"{icon} {status} {acc['account_name']} (@{acc.get('username', 'N/A')})")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def add_account_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add a new social media account. Usage: /add_account tiktok MyShop @myshop"""
    if not is_admin(update.effective_user.id):
        return

    args = context.args
    if len(args) < 3:
        await update.message.reply_text(
            "📝 Cách dùng:\n"
            "`/add_account <platform> <tên> <username>`\n\n"
            "Ví dụ:\n"
            "`/add_account tiktok ShopThoiTrang @shoptt01`\n"
            "`/add_account facebook FanpageTT page_id_123`",
            parse_mode="Markdown",
        )
        return

    platform, name, username = args[0].lower(), args[1], args[2]
    if platform not in ("tiktok", "facebook"):
        await update.message.reply_text("❌ Platform phải là 'tiktok' hoặc 'facebook'")
        return

    acc_id = await execute_insert(
        "INSERT INTO accounts (platform, account_name, username) VALUES (?, ?, ?)",
        (platform, name, username.lstrip("@")),
    )

    await update.message.reply_text(
        f"✅ Đã thêm tài khoản #{acc_id}:\n"
        f"{'🎵' if platform == 'tiktok' else '📘'} {name} (@{username})"
    )


async def schedule_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show upcoming scheduled posts."""
    if not is_admin(update.effective_user.id):
        return

    upcoming = await execute_query(
        """SELECT s.*, v.caption_tiktok, a.account_name, a.platform
           FROM schedule s
           JOIN videos v ON s.video_id = v.id
           JOIN accounts a ON s.account_id = a.id
           WHERE s.status = 'pending'
           ORDER BY s.scheduled_at
           LIMIT 10"""
    )

    if not upcoming:
        await update.message.reply_text("📅 Không có bài nào trong lịch.")
        return

    lines = ["📅 **Lịch đăng sắp tới:**\n"]
    for s in upcoming:
        icon = "🎵" if s["platform"] == "tiktok" else "📘"
        lines.append(
            f"{icon} {s['scheduled_at'][:16]} — {s['account_name']}\n"
            f"   📝 {(s.get('caption_tiktok') or '')[:50]}..."
        )

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cleanup_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manually trigger cleanup."""
    if not is_admin(update.effective_user.id):
        return

    msg = await update.message.reply_text("🧹 Đang dọn dẹp...")
    result = await run_cleanup()
    await msg.edit_text(
        "✅ **Dọn dẹp hoàn tất!**\n\n"
        f"🗑️ Temp: {result['temp_deleted']} files\n"
        f"🗑️ Local videos: {result['local_videos_deleted']}\n"
        f"🗑️ R2 videos: {result['r2_videos_deleted']}\n"
        f"💾 Freed: {result['bytes_freed'] / (1024*1024):.1f}MB",
        parse_mode="Markdown",
    )
