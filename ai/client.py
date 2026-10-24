"""
Google AI client initialization.
Sets up Gemini client using the new google.genai SDK.
"""

import logging

from google import genai

from config import GoogleConfig

logger = logging.getLogger(__name__)

_client = None


def init_gemini() -> None:
    """Initialize Google GenAI client."""
    global _client

    if not GoogleConfig.API_KEY:
        logger.warning("⚠️ GEMINI_API_KEY not set — Gemini features disabled")
        return

    _client = genai.Client(api_key=GoogleConfig.API_KEY)
    logger.info(f"✅ Gemini initialized — model: {GoogleConfig.GEMINI_MODEL}")


def get_client() -> genai.Client:
    """Get the initialized GenAI client instance."""
    if _client is None:
        init_gemini()
    if _client is None:
        raise RuntimeError("Gemini not configured. Set GEMINI_API_KEY in .env")
    return _client
