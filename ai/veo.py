"""
Google Veo 3.1 — AI Video Generation (Image → Video).
Uses Vertex AI API for cinematic product video creation.
Based on: https://github.com/google/skills (veo-use/veo-build)
"""

import asyncio
import logging
import time
from pathlib import Path
from typing import Optional

from config import GoogleConfig, TEMP_DIR, VEO_PRODUCT_PROMPT

logger = logging.getLogger(__name__)


class VeoService:
    """Wrapper for Google Veo 3.1 video generation."""

    def __init__(self):
        self._client = None
        self._initialized = False

    def _ensure_initialized(self):
        """Lazy-initialize the Vertex AI client."""
        if self._initialized:
            return

        if not GoogleConfig.PROJECT_ID or GoogleConfig.PROJECT_ID == "your_project_id":
            raise RuntimeError(
                "GOOGLE_CLOUD_PROJECT not set. "
                "Please configure Google Cloud credentials."
            )

        try:
            from google import genai

            self._client = genai.Client(
                vertexai=True,
                project=GoogleConfig.PROJECT_ID,
                location="us-central1",
            )
            self._initialized = True
            logger.info(f"✅ Veo initialized — model: {GoogleConfig.VEO_MODEL}")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Veo client: {e}")
            raise

    async def image_to_video(
        self,
        image_path: str,
        prompt: str = "",
        product_name: str = "",
        duration_seconds: int = 0,
        aspect_ratio: str = "",
        tier: str = "",
        output_path: str = "",
    ) -> Optional[str]:
        """
        Generate a video from a product image using Veo 3.1.

        Args:
            image_path: Path to the source product image.
            prompt: Custom prompt for video generation.
            product_name: Product name (used for default prompt).
            duration_seconds: Video duration (4, 6, or 8).
            aspect_ratio: Aspect ratio ('9:16', '16:9').
            tier: Veo tier ('lite', 'fast', 'standard').
            output_path: Where to save the generated video.

        Returns:
            Path to the generated video file, or None on failure.
        """
        self._ensure_initialized()

        from google.genai import types

        # Defaults
        duration_seconds = duration_seconds or int(GoogleConfig.VEO_DURATION.replace('s', ''))
        aspect_ratio = aspect_ratio or GoogleConfig.VEO_ASPECT_RATIO
        tier = tier or GoogleConfig.VEO_TIER

        # Build prompt
        if not prompt:
            prompt = VEO_PRODUCT_PROMPT.format(
                product_name=product_name or "product",
                motion_type="360 degree rotation",
                background="white",
            )

        # Prepare output path
        if not output_path:
            output_path = str(
                TEMP_DIR / f"veo_{Path(image_path).stem}_{int(time.time())}.mp4"
            )

        try:
            image_path = Path(image_path)
            if not image_path.exists():
                raise FileNotFoundError(f"Image not found: {image_path}")

            logger.info(
                f"🎬 Veo generating video — tier: {tier}, "
                f"duration: {duration_seconds}s, model: {GoogleConfig.VEO_MODEL}"
            )

            # Load image using types.Image (correct SDK usage)
            image = types.Image.from_file(location=str(image_path))

            # Submit generation request
            operation = self._client.models.generate_videos(
                model=GoogleConfig.VEO_MODEL,
                prompt=prompt,
                image=image,
                config=types.GenerateVideosConfig(
                    aspect_ratio=aspect_ratio,
                    duration_seconds=duration_seconds,
                    number_of_videos=1,
                    enhance_prompt=True,
                    generate_audio=True,
                ),
            )

            logger.info(f"⏳ Veo operation submitted: {operation.name}")

            # Poll for result
            result = await self._poll_operation(operation)

            if result and result.generated_videos:
                # Save video
                output = Path(output_path)
                output.parent.mkdir(parents=True, exist_ok=True)
                result.generated_videos[0].video.save(str(output))

                # Estimate cost
                cost = self._estimate_cost(tier, duration_seconds)
                file_size = output.stat().st_size / (1024 * 1024)

                logger.info(
                    f"✅ Veo video saved — {output} "
                    f"({file_size:.1f}MB, est. cost: ${cost:.2f})"
                )
                return str(output)
            else:
                logger.error("❌ Veo returned no video")
                return None

        except Exception as e:
            logger.error(f"❌ Veo generation failed: {e}")
            return None

    async def _poll_operation(self, operation, timeout: int = 300, interval: int = 10):
        """Poll a long-running operation until completion."""
        start = time.time()
        while time.time() - start < timeout:
            try:
                op_status = self._client.operations.get(operation)
                if op_status.done:
                    logger.info(f"✅ Veo rendering complete ({int(time.time() - start)}s)")
                    return op_status.result
            except Exception as e:
                logger.debug(f"⏳ Poll check: {e}")

            elapsed = int(time.time() - start)
            logger.info(f"⏳ Veo rendering... {elapsed}s / {timeout}s")
            await asyncio.sleep(interval)

        logger.error(f"❌ Veo operation timed out after {timeout}s")
        return None

    def _estimate_cost(self, tier: str, duration_seconds: int) -> float:
        """Estimate USD cost for a Veo generation."""
        # 2026 pricing: per second of generated video
        rates = {
            "lite": 0.05,
            "fast": 0.10,
            "standard": 0.50,
        }
        rate = rates.get(tier, 0.10)
        return rate * duration_seconds


# Singleton instance
veo_service = VeoService()
