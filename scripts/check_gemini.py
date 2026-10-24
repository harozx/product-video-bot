"""Quick test for Gemini API connection."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from ai.client import init_gemini, get_client
from ai.gemini import generate_caption
from config import GoogleConfig


async def test():
    print("🔑 Testing Gemini API key...")
    init_gemini()
    client = get_client()

    # Simple test
    response = await client.aio.models.generate_content(
        model=GoogleConfig.GEMINI_MODEL,
        contents="Trả lời ngắn gọn: 1 + 1 = ?",
    )
    print(f"✅ Gemini connected! Response: {response.text.strip()}")

    # Test caption generation
    print("\n📝 Testing caption generation...")
    captions = await generate_caption(
        product_name="Áo thun unisex oversize",
        price="199K",
        features="Cotton 100%, form rộng, nhiều màu",
        niche="fashion",
    )
    print(f"✅ TikTok caption: {captions['caption_tiktok'][:100]}...")
    print(f"✅ Hashtags: {', '.join(captions['hashtags'][:5])}")
    print("\n🎉 Gemini API working perfectly!")


asyncio.run(test())
