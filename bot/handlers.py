"""
Telegram Bot — Main message and media handlers.
Conversation flow: receive images → product info → create video → approve → schedule.
"""

import json
import logging
from pathlib import Path

from telegram import Update
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    MessageHandler, CallbackQueryHandler, filters,
)

from ai.gemini import generate_caption, generate_veo_prompt, generate_review_script
from ai.veo import veo_service
from engine.turbo_client import create_video_from_topic, create_video_with_images, check_turbo_health
from bot.keyboards import (
    video_approval_keyboard, platform_select_keyboard,
    veo_tier_keyboard, schedule_time_keyboard, account_select_keyboard,
)
from config import TelegramConfig, TEMP_DIR, GoogleConfig
from database import execute_insert, execute_query
from engine.composer import create_slideshow
from storage.r2_client import upload_file

logger = logging.getLogger(__name__)

# Conversation states
(WAITING_IMAGES, WAITING_NAME, WAITING_PRICE, WAITING_TIER,
 WAITING_APPROVAL, WAITING_PLATFORM, WAITING_ACCOUNT, WAITING_SCHEDULE) = range(8)


def is_admin(user_id: int) -> bool:
    # If admin IDs are not configured, deny everyone and log the ID so the owner can add it
    if not TelegramConfig.ADMIN_IDS:
        logger.warning(f"🔑 ADMIN NOT SET — User ID: {user_id} (add this to TELEGRAM_ADMIN_IDS in .env)")
        return False
    return user_id in TelegramConfig.ADMIN_IDS


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("⛔ Không có quyền.")
        return ConversationHandler.END

    await update.message.reply_text(
        f"👋 Chào {user.first_name}!\n\n"
        "🤖 **Auto Content Pipeline** sẵn sàng!\n\n"
        "📸 Gửi ảnh sản phẩm để bắt đầu.\n"
        "💡 Gửi 1 ảnh → Veo AI video\n"
        "💡 Gửi 3-10 ảnh → FFmpeg slideshow\n"
        "💡 /help để xem lệnh",
        parse_mode="Markdown",
    )
    context.user_data.clear()
    context.user_data["images"] = []
    return WAITING_IMAGES


async def image_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END

    photo = update.message.photo[-1]
    file = await photo.get_file()
    image_dir = TEMP_DIR / "incoming"
    image_dir.mkdir(parents=True, exist_ok=True)
    image_path = str(image_dir / f"{photo.file_unique_id}.jpg")
    await file.download_to_drive(image_path)

    if "images" not in context.user_data:
        context.user_data["images"] = []
    context.user_data["images"].append(image_path)

    count = len(context.user_data["images"])
    await update.message.reply_text(
        f"📸 Đã nhận {count} ảnh.\n"
        "Gửi thêm hoặc nhập **tên sản phẩm**:",
        parse_mode="Markdown",
    )
    return WAITING_NAME


async def name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        return await image_handler(update, context)
    context.user_data["product_name"] = update.message.text.strip()
    await update.message.reply_text(
        f"📝 SP: **{context.user_data['product_name']}**\n"
        "💰 Nhập giá (hoặc `skip`):",
        parse_mode="Markdown",
    )
    return WAITING_PRICE


async def price_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    context.user_data["price"] = "" if text.lower() == "skip" else text

    # Luôn hiện menu chọn kiểu video
    await update.message.reply_text(
        "🎬 Chọn cách tạo video:\n\n"
        "🎤 **AI Review** — Ảnh SP + giọng AI đọc review + phụ đề\n"
        "🎥 **Stock Video** — Video stock + giọng AI + phụ đề\n"
        "⚡ **Veo** — AI tạo video từ ảnh (tốn phí)\n"
        "🎬 **Slideshow** — Ảnh ghép đơn giản",
        parse_mode="Markdown",
        reply_markup=veo_tier_keyboard(),
    )
    return WAITING_TIER


async def tier_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tier = query.data.split(":")[1]
    context.user_data["tier"] = tier

    tier_labels = {
        "turbo_review": "🎤 AI Review (ảnh SP + voice + sub)",
        "turbo_stock": "🎥 Stock Video (voice + sub)",
        "lite": "⚡ Veo Lite",
        "standard": "💎 Veo Pro",
        "ffmpeg": "🎬 Slideshow",
    }
    label = tier_labels.get(tier, tier)
    await query.edit_message_text(f"✅ {label}\n🎬 Đang tạo video... ⏳")
    return await _create_video(update, context)


async def _create_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Core video creation: caption → video → upload → preview."""
    images = context.user_data.get("images", [])
    product_name = context.user_data.get("product_name", "Sản phẩm")
    price = context.user_data.get("price", "")
    tier = context.user_data.get("tier", "ffmpeg")

    chat = update.effective_chat
    if update.callback_query:
        chat = update.callback_query.message.chat

    msg = await chat.send_message("⏳ 1/3: Tạo caption...")

    # 1. Generate caption
    try:
        captions = await generate_caption(product_name, price)
    except Exception:
        captions = {
            "caption_tiktok": f"🔥 {product_name}",
            "caption_facebook": f"✨ {product_name}",
            "hashtags": ["#trending", "#fyp"],
        }

    # 2. Create video
    await msg.edit_text("⏳ 2/3: Tạo video...")
    video_path = None

    if tier == "turbo_review":
        # AI Review: Gemini Vision nhìn ảnh → viết script → voice + subtitle
        try:
            await msg.edit_text("⏳ 2/3: AI đang phân tích ảnh + viết script...")
            first_image = images[0] if images else ""
            script = await generate_review_script(product_name, first_image, price)
            await msg.edit_text(f"⏳ 2/3: Tạo video (voice + sub)...\n📝 {script[:80]}...")

            if images:
                video_path = await create_video_with_images(
                    subject=product_name,
                    image_paths=images,
                    video_script=script,
                )
            else:
                video_path = await create_video_from_topic(
                    subject=product_name,
                    video_script=script,
                )
        except Exception as e:
            logger.error(f"Turbo review failed: {e}")
            await chat.send_message(f"⚠️ AI Review lỗi: {e}\n→ Fallback slideshow")

    elif tier == "turbo_stock":
        # Stock video: Gemini tạo script → Pexels stock footage + voice + subtitle
        try:
            await msg.edit_text("⏳ 2/3: AI đang viết script review...")
            script = await generate_review_script(product_name, price=price)
            await msg.edit_text(f"⏳ 2/3: Tạo video stock + voice...\n📝 {script[:80]}...")
            video_path = await create_video_from_topic(
                subject=product_name,
                video_script=script,
            )
        except Exception as e:
            logger.error(f"Turbo stock failed: {e}")
            await chat.send_message(f"⚠️ Stock Video lỗi: {e}\n→ Fallback slideshow")

    elif tier in ("lite", "fast", "standard"):
        try:
            veo_prompt = await generate_veo_prompt(product_name)
            video_path = await veo_service.image_to_video(
                image_path=images[0], prompt=veo_prompt,
                product_name=product_name, tier=tier,
            )
        except Exception as e:
            logger.error(f"Veo failed: {e}")
            await chat.send_message("⚠️ Veo lỗi → FFmpeg fallback")

    if not video_path:
        video_path = await create_slideshow(
            image_paths=images,
            text_overlay=product_name,
            price_overlay=price,
        )

    if not video_path:
        await msg.edit_text("❌ Tạo video thất bại!")
        return ConversationHandler.END

    # 3. Upload to R2
    await msg.edit_text("⏳ 3/3: Upload...")
    r2_url = upload_file(video_path, f"videos/{Path(video_path).name}")

    # 4. Save to database
    product_id = await execute_insert(
        "INSERT INTO products (name, price) VALUES (?, ?)",
        (product_name, price),
    )
    for img in images:
        await execute_insert(
            "INSERT INTO media (product_id, file_path, type) VALUES (?, ?, 'image')",
            (product_id, img),
        )

    video_id = await execute_insert(
        """INSERT INTO videos
           (product_id, template, veo_tier, file_path, r2_key, r2_url,
            caption_tiktok, caption_facebook, hashtags, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'ready')""",
        (product_id, "veo" if tier != "ffmpeg" else "slideshow",
         tier if tier != "ffmpeg" else None, video_path,
         f"videos/{Path(video_path).name}" if r2_url else None,
         r2_url, captions["caption_tiktok"], captions["caption_facebook"],
         json.dumps(captions["hashtags"])),
    )
    context.user_data["current_video_id"] = video_id

    # 5. Send preview
    await msg.delete()
    hashtags_str = " ".join(captions["hashtags"][:5])
    caption_preview = (
        f"🎬 **Video #{video_id}** — {product_name}\n"
        f"{'💰 ' + price if price else ''}\n\n"
        f"📝 {captions['caption_tiktok']}\n\n"
        f"🏷️ {hashtags_str}"
    )

    with open(video_path, "rb") as vf:
        await chat.send_video(
            video=vf, caption=caption_preview, parse_mode="Markdown",
            reply_markup=video_approval_keyboard(video_id),
            supports_streaming=True,
        )
    return WAITING_APPROVAL


async def approval_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action, video_id = query.data.split(":", 1)
    video_id = int(video_id)

    if action == "post_now":
        await query.edit_message_reply_markup(
            reply_markup=platform_select_keyboard(video_id))
        return WAITING_PLATFORM
    elif action == "schedule":
        await query.edit_message_reply_markup(
            reply_markup=schedule_time_keyboard(video_id))
        return WAITING_SCHEDULE
    elif action == "regenerate":
        await query.edit_message_text("🔄 Đang tạo lại...")
        return await _create_video(update, context)
    elif action == "cancel":
        await query.edit_message_text("❌ Đã hủy.")
        return ConversationHandler.END
    return WAITING_APPROVAL


async def platform_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, video_id = query.data.rsplit(":", 1)
    video_id = int(video_id)

    platform = "both"
    if "tiktok" in query.data:
        platform = "tiktok"
    elif "fb" in query.data:
        platform = "facebook"

    context.user_data["post_platform"] = platform
    platforms = ("tiktok", "facebook") if platform == "both" else (platform,)
    placeholders = ",".join("?" * len(platforms))
    accounts = await execute_query(
        f"SELECT * FROM accounts WHERE platform IN ({placeholders}) AND status='active'",
        platforms,
    )

    if not accounts:
        await query.edit_message_text(f"⚠️ Chưa có tài khoản {platform}!\nDùng /add_account")
        return ConversationHandler.END

    await query.edit_message_reply_markup(
        reply_markup=account_select_keyboard(accounts, video_id, platform))
    return WAITING_ACCOUNT


async def schedule_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("time:"):
        parts = query.data.split(":")
        video_id, hour, minute = int(parts[1]), parts[2], parts[3]
        from datetime import datetime, timedelta
        now = datetime.now()
        scheduled = now.replace(hour=int(hour), minute=int(minute), second=0)
        if scheduled <= now:
            scheduled += timedelta(days=1)
        context.user_data["scheduled_at"] = scheduled.isoformat()
        await query.edit_message_text(
            f"⏰ Lên lịch **{hour}:{minute}** ({scheduled.strftime('%d/%m')})\nChọn platform:",
            parse_mode="Markdown",
            reply_markup=platform_select_keyboard(video_id),
        )
        return WAITING_PLATFORM
    return WAITING_SCHEDULE


async def account_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("account:"):
        _, video_id, account_id, platform = data.split(":")
        video_id, account_id = int(video_id), int(account_id)
        from datetime import datetime
        sched_at = context.user_data.get("scheduled_at", datetime.now().isoformat())
        status = "pending" if context.user_data.get("scheduled_at") else "posting"

        await execute_insert(
            "INSERT INTO schedule (video_id, account_id, platform, scheduled_at, status) VALUES (?,?,?,?,?)",
            (video_id, account_id, platform, sched_at, status),
        )
        await query.edit_message_text(f"✅ {'Đã lên lịch' if status == 'pending' else 'Đang đăng'}!")
        context.user_data.clear()
        context.user_data["images"] = []
        return ConversationHandler.END

    elif data.startswith("account_all:"):
        _, video_id, platform = data.split(":")
        video_id = int(video_id)
        from datetime import datetime
        sched_at = context.user_data.get("scheduled_at", datetime.now().isoformat())
        accounts = await execute_query(
            "SELECT * FROM accounts WHERE platform = ? AND status='active'", (platform,))
        for acc in accounts:
            await execute_insert(
                "INSERT INTO schedule (video_id, account_id, platform, scheduled_at, status) VALUES (?,?,?,?,'pending')",
                (video_id, acc["id"], platform, sched_at),
            )
        await query.edit_message_text(f"✅ Lên lịch cho {len(accounts)} tài khoản!")
        context.user_data.clear()
        context.user_data["images"] = []
        return ConversationHandler.END

    return WAITING_ACCOUNT


def build_conversation_handler() -> ConversationHandler:
    """Build the main conversation handler."""
    return ConversationHandler(
        entry_points=[
            CommandHandler("start", start_handler),
            MessageHandler(filters.PHOTO, image_handler),
        ],
        states={
            WAITING_IMAGES: [
                MessageHandler(filters.PHOTO, image_handler),
                MessageHandler(filters.TEXT & ~filters.COMMAND, name_handler),
            ],
            WAITING_NAME: [
                MessageHandler(filters.PHOTO, image_handler),
                MessageHandler(filters.TEXT & ~filters.COMMAND, name_handler),
            ],
            WAITING_PRICE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, price_handler),
            ],
            WAITING_TIER: [
                CallbackQueryHandler(tier_callback, pattern=r"^tier:"),
            ],
            WAITING_APPROVAL: [
                CallbackQueryHandler(approval_callback,
                    pattern=r"^(post_now|schedule|edit_caption|regenerate|cancel):"),
            ],
            WAITING_PLATFORM: [
                CallbackQueryHandler(platform_callback, pattern=r"^platform_"),
                CallbackQueryHandler(approval_callback, pattern=r"^back_approval:"),
            ],
            WAITING_SCHEDULE: [
                CallbackQueryHandler(schedule_callback, pattern=r"^time"),
                CallbackQueryHandler(approval_callback, pattern=r"^back_approval:"),
            ],
            WAITING_ACCOUNT: [
                CallbackQueryHandler(account_callback, pattern=r"^account"),
                CallbackQueryHandler(platform_callback, pattern=r"^back_platform:"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", lambda u, c: ConversationHandler.END),
            CommandHandler("start", start_handler),
        ],
        per_user=True, per_chat=True,
    )
