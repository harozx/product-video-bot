"""
Gemini 2.5 Flash — Caption & Hashtag Generation.
Uses free tier (1,500 req/day) for all text generation tasks.
"""

import json
import logging
from typing import Optional

from google.genai import types

from ai.client import get_client
from config import GoogleConfig, CAPTION_PROMPT

logger = logging.getLogger(__name__)


async def generate_caption(
    product_name: str,
    price: str = "",
    features: str = "",
    niche: str = "general",
) -> dict:
    """
    Generate TikTok & Facebook captions + hashtags for a product.

    Returns:
        {
            "caption_tiktok": "...",
            "caption_facebook": "...",
            "hashtags": ["#tag1", "#tag2", ...]
        }
    """
    client = get_client()

    prompt = CAPTION_PROMPT.format(
        product_name=product_name,
        price=price or "Liên hệ",
        features=features or "Chất lượng cao",
        niche=niche,
    )

    try:
        response = await client.aio.models.generate_content(
            model=GoogleConfig.GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.8,
                top_p=0.95,
                max_output_tokens=2048,
                response_mime_type="application/json",
            ),
        )
        result = json.loads(response.text)

        if not all(k in result for k in ("caption_tiktok", "caption_facebook", "hashtags")):
            raise ValueError("Missing required fields in response")

        logger.info(f"✅ Caption generated for '{product_name}' — {len(result['hashtags'])} hashtags")
        return result

    except json.JSONDecodeError as e:
        logger.error(f"❌ Failed to parse Gemini JSON: {e}")
        return _fallback_caption(product_name, price)
    except Exception as e:
        logger.error(f"❌ Gemini caption generation failed: {e}")
        return _fallback_caption(product_name, price)


async def generate_review_script(
    product_name: str,
    image_path: str = "",
    price: str = "",
    language: str = "vi",
) -> str:
    """
    Gemini Vision: nhìn ảnh sản phẩm → viết script review ~30 giây.
    Nếu không có ảnh, tạo script từ tên sản phẩm.
    
    Returns:
        Script text for TTS voiceover (~80-120 từ tiếng Việt)
    """
    client = get_client()
    
    prompt = f"""Bạn là content creator chuyên review sản phẩm trên TikTok/Reels.
Viết một đoạn script review sản phẩm cho video ngắn (25-35 giây khi đọc).

Sản phẩm: {product_name}
{"Giá: " + price if price else ""}

YÊU CẦU:
- Tiếng Việt tự nhiên, dễ nghe, hấp dẫn
- 80-120 từ (vừa đủ 30 giây đọc)
- Mở đầu thu hút (hook câu đầu)
- Mô tả đặc điểm, chất liệu, thiết kế (dựa trên ảnh nếu có)
- Kết thúc bằng call-to-action (inbox, link bio...)
- KHÔNG dùng markdown, emoji, ký hiệu đặc biệt
- KHÔNG ghi "voiceover", "narrator", chỉ viết nội dung đọc
- CHỈ trả về script text thuần, không giải thích"""

    try:
        contents = []
        
        # Nếu có ảnh → dùng Gemini Vision
        if image_path:
            from pathlib import Path
            img_data = Path(image_path).read_bytes()
            
            # Determine mime type
            ext = Path(image_path).suffix.lower()
            mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
            mime_type = mime_map.get(ext, "image/jpeg")
            
            contents = [
                types.Part.from_bytes(data=img_data, mime_type=mime_type),
                prompt,
            ]
            logger.info(f"📸 Gemini Vision analyzing: {image_path}")
        else:
            contents = [prompt]
        
        response = await client.aio.models.generate_content(
            model=GoogleConfig.GEMINI_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=0.7,
                max_output_tokens=1024,
            ),
        )
        
        script = response.text.strip()
        # Clean up any markdown artifacts
        script = script.replace("*", "").replace("#", "").replace("`", "")
        
        word_count = len(script.split())
        logger.info(f"✅ Review script generated: {word_count} words for '{product_name}'")
        return script
        
    except Exception as e:
        logger.error(f"❌ Review script generation failed: {e}")
        return (
            f"Xin chào các bạn, hôm nay mình sẽ review {product_name}. "
            f"Sản phẩm này có thiết kế rất đẹp mắt và chất lượng tuyệt vời. "
            f"{'Với mức giá ' + price + ', ' if price else ''}"
            f"đây thực sự là một lựa chọn đáng để bạn sở hữu. "
            f"Nếu bạn quan tâm, hãy inbox mình hoặc xem link ở bio nhé."
        )


async def generate_veo_prompt(
    product_name: str,
    category: str = "",
    style: str = "professional",
) -> str:
    """Use Gemini to generate an optimized prompt for Veo video generation."""
    client = get_client()

    prompt = f"""Bạn là chuyên gia prompt engineering cho AI video generation (Google Veo).
Viết một prompt TIẾNG ANH tối ưu để tạo video quay sản phẩm.

Sản phẩm: {product_name}
Loại: {category or 'general'}
Phong cách: {style}

YÊU CẦU:
- Tiếng Anh, ngắn gọn (dưới 50 từ)
- Mô tả chuyển động camera
- Mô tả ánh sáng và background
- Phong cách commercial/cinematic
- KHÔNG mention text overlay

Chỉ trả về prompt text, không giải thích."""

    try:
        response = await client.aio.models.generate_content(
            model=GoogleConfig.GEMINI_MODEL,
            contents=prompt,
        )
        veo_prompt = response.text.strip().strip('"').strip("'")
        logger.info(f"✅ Veo prompt generated for '{product_name}'")
        return veo_prompt
    except Exception as e:
        logger.error(f"❌ Veo prompt generation failed: {e}")
        return (
            f"Cinematic product showcase of {product_name}. "
            "Smooth 360 rotation, soft studio lighting, "
            "clean white background, commercial photography style, 4K detail."
        )


async def generate_schedule_suggestion(
    platform: str,
    niche: str = "general",
    timezone: str = "Asia/Ho_Chi_Minh",
) -> dict:
    """Ask Gemini for optimal posting times."""
    client = get_client()

    prompt = f"""Bạn là chuyên gia social media marketing tại Việt Nam.
Gợi ý 3 khung giờ đăng bài tốt nhất cho:
- Platform: {platform}
- Niche: {niche}
- Timezone: {timezone}

Trả về JSON:
{{
    "slots": [
        {{"hour": 19, "minute": 0, "reason": "..."}},
        {{"hour": 21, "minute": 0, "reason": "..."}},
        {{"hour": 7, "minute": 30, "reason": "..."}}
    ]
}}"""

    try:
        response = await client.aio.models.generate_content(
            model=GoogleConfig.GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )
        return json.loads(response.text)
    except Exception:
        return {
            "slots": [
                {"hour": 7, "minute": 0, "reason": "Buổi sáng"},
                {"hour": 12, "minute": 0, "reason": "Giờ nghỉ trưa"},
                {"hour": 19, "minute": 0, "reason": "Tối, peak engagement"},
            ]
        }


def _fallback_caption(product_name: str, price: str) -> dict:
    """Fallback when Gemini is unavailable."""
    return {
        "caption_tiktok": f"🔥 {product_name} {'- ' + price if price else ''}\n💬 Inbox để đặt hàng!",
        "caption_facebook": f"✨ {product_name}\n{'💰 Giá: ' + price if price else ''}\n📩 Inbox để được tư vấn!",
        "hashtags": [
            "#trending", "#fyp", "#viral", "#xuhuong",
            "#muasam", "#shopping", "#sale", "#review",
        ],
    }
