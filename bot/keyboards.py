"""
Telegram Bot inline keyboards.
Reusable keyboard builders for the conversation flow.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def video_approval_keyboard(video_id: int) -> InlineKeyboardMarkup:
    """Keyboard shown after video preview — approve, edit, or cancel."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Đăng ngay", callback_data=f"post_now:{video_id}"),
            InlineKeyboardButton("⏰ Lên lịch", callback_data=f"schedule:{video_id}"),
        ],
        [
            InlineKeyboardButton("✏️ Sửa caption", callback_data=f"edit_caption:{video_id}"),
            InlineKeyboardButton("🔄 Tạo lại", callback_data=f"regenerate:{video_id}"),
        ],
        [
            InlineKeyboardButton("❌ Hủy", callback_data=f"cancel:{video_id}"),
        ],
    ])


def platform_select_keyboard(video_id: int) -> InlineKeyboardMarkup:
    """Select which platforms to post to."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎵 TikTok", callback_data=f"platform_tiktok:{video_id}"),
            InlineKeyboardButton("📘 Facebook", callback_data=f"platform_fb:{video_id}"),
        ],
        [
            InlineKeyboardButton("📤 Cả hai", callback_data=f"platform_both:{video_id}"),
        ],
        [
            InlineKeyboardButton("⬅️ Quay lại", callback_data=f"back_approval:{video_id}"),
        ],
    ])


def account_select_keyboard(accounts: list[dict], video_id: int, platform: str) -> InlineKeyboardMarkup:
    """Select which account to post from."""
    buttons = []
    for acc in accounts:
        status_icon = "🟢" if acc["status"] == "active" else "🔴"
        buttons.append([
            InlineKeyboardButton(
                f"{status_icon} {acc['account_name']}",
                callback_data=f"account:{video_id}:{acc['id']}:{platform}",
            )
        ])

    buttons.append([
        InlineKeyboardButton("📤 Tất cả accounts", callback_data=f"account_all:{video_id}:{platform}"),
    ])
    buttons.append([
        InlineKeyboardButton("⬅️ Quay lại", callback_data=f"back_platform:{video_id}"),
    ])

    return InlineKeyboardMarkup(buttons)


def schedule_time_keyboard(video_id: int) -> InlineKeyboardMarkup:
    """Quick schedule time selection."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🌅 7:00", callback_data=f"time:{video_id}:07:00"),
            InlineKeyboardButton("☀️ 12:00", callback_data=f"time:{video_id}:12:00"),
            InlineKeyboardButton("🌆 17:00", callback_data=f"time:{video_id}:17:00"),
        ],
        [
            InlineKeyboardButton("🌙 19:00", callback_data=f"time:{video_id}:19:00"),
            InlineKeyboardButton("🌃 21:00", callback_data=f"time:{video_id}:21:00"),
            InlineKeyboardButton("🕐 Custom", callback_data=f"time_custom:{video_id}"),
        ],
        [
            InlineKeyboardButton("⬅️ Quay lại", callback_data=f"back_approval:{video_id}"),
        ],
    ])


def veo_tier_keyboard() -> InlineKeyboardMarkup:
    """Select video creation mode."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎤 AI Review (FREE)", callback_data="tier:turbo_review"),
        ],
        [
            InlineKeyboardButton("🎥 Stock Video (FREE)", callback_data="tier:turbo_stock"),
        ],
        [
            InlineKeyboardButton("⚡ Veo Lite (~$0.30)", callback_data="tier:lite"),
            InlineKeyboardButton("💎 Veo Pro (~$3)", callback_data="tier:standard"),
        ],
        [
            InlineKeyboardButton("🎬 Slideshow (FREE)", callback_data="tier:ffmpeg"),
        ],
    ])


def confirm_keyboard(action: str, target_id: int) -> InlineKeyboardMarkup:
    """Generic yes/no confirmation."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Có", callback_data=f"confirm_yes:{action}:{target_id}"),
            InlineKeyboardButton("❌ Không", callback_data=f"confirm_no:{action}:{target_id}"),
        ],
    ])
