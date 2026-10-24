"""
FFmpeg-based video composition engine.
Creates slideshow videos from product images with transitions, music, and text.
Used as a fallback when Veo is not available, or for basic content.
"""

import asyncio
import logging
import random
from pathlib import Path
from typing import Optional

from PIL import Image

from config import (
    VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_FPS,
    DEFAULT_CLIP_DURATION, TRANSITION_DURATION,
    TEMP_DIR, MUSIC_DIR,
)

logger = logging.getLogger(__name__)


async def create_slideshow(
    image_paths: list[str],
    output_path: str = "",
    music_path: str = "",
    duration_per_image: float = DEFAULT_CLIP_DURATION,
    text_overlay: str = "",
    price_overlay: str = "",
    transition: str = "fade",
) -> Optional[str]:
    """
    Create a vertical video slideshow from product images.
    Uses FFmpeg directly for maximum performance on i5.

    Args:
        image_paths: List of image file paths.
        music_path: Background music file path.
        duration_per_image: Seconds each image is shown.
        text_overlay: Product name overlay.
        price_overlay: Price overlay.
        transition: Transition type ('fade', 'slide', 'zoom').

    Returns:
        Path to the created video file.
    """
    if not image_paths:
        raise ValueError("No images provided")

    # Prepare output
    if not output_path:
        output_path = str(TEMP_DIR / f"slideshow_{int(asyncio.get_event_loop().time())}.mp4")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    # Prepare images (resize to 1080x1920)
    prepared_images = []
    for img_path in image_paths:
        prepared = await _prepare_image(img_path)
        if prepared:
            prepared_images.append(prepared)

    if not prepared_images:
        raise ValueError("No valid images after preparation")

    # Pick music
    if not music_path:
        music_path = _pick_random_music()

    # Calculate total duration
    total_duration = len(prepared_images) * duration_per_image

    try:
        # Build FFmpeg command
        cmd = _build_ffmpeg_command(
            images=prepared_images,
            output=str(output),
            music=music_path,
            duration_per_image=duration_per_image,
            total_duration=total_duration,
            text=text_overlay,
            price=price_overlay,
            transition=transition,
        )

        logger.info(f"🎬 Rendering slideshow — {len(prepared_images)} images, {total_duration}s")

        # Run FFmpeg
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            file_size = output.stat().st_size / (1024 * 1024)
            logger.info(f"✅ Slideshow created — {output} ({file_size:.1f}MB)")
            return str(output)
        else:
            logger.error(f"❌ FFmpeg failed: {stderr.decode()[:500]}")
            return None

    except FileNotFoundError:
        logger.error("❌ FFmpeg not found. Please install FFmpeg.")
        return None
    except Exception as e:
        logger.error(f"❌ Slideshow creation failed: {e}")
        return None
    finally:
        # Cleanup prepared images
        for p in prepared_images:
            try:
                Path(p).unlink(missing_ok=True)
            except Exception:
                pass


async def _prepare_image(image_path: str) -> Optional[str]:
    """
    Resize and pad an image to 1080x1920 (9:16).
    Uses center crop with blur background fill.
    """
    try:
        img = Image.open(image_path).convert("RGB")

        # Target dimensions
        target_w, target_h = VIDEO_WIDTH, VIDEO_HEIGHT
        target_ratio = target_w / target_h

        # Current ratio
        img_ratio = img.width / img.height

        if abs(img_ratio - target_ratio) < 0.01:
            # Already correct ratio — just resize
            img = img.resize((target_w, target_h), Image.LANCZOS)
        else:
            # Create blurred background
            bg = img.copy().resize((target_w, target_h), Image.LANCZOS)
            try:
                from PIL import ImageFilter
                bg = bg.filter(ImageFilter.GaussianBlur(radius=30))
            except Exception:
                pass

            # Fit image within bounds
            if img_ratio > target_ratio:
                # Wider — fit width
                new_w = target_w
                new_h = int(target_w / img_ratio)
            else:
                # Taller — fit height
                new_h = target_h
                new_w = int(target_h * img_ratio)

            img_resized = img.resize((new_w, new_h), Image.LANCZOS)

            # Paste centered on blurred background
            x = (target_w - new_w) // 2
            y = (target_h - new_h) // 2
            bg.paste(img_resized, (x, y))
            img = bg

        # Save prepared image
        prepared_path = str(TEMP_DIR / f"prep_{Path(image_path).stem}.jpg")
        img.save(prepared_path, "JPEG", quality=95)
        return prepared_path

    except Exception as e:
        logger.error(f"❌ Failed to prepare image {image_path}: {e}")
        return None


def _build_ffmpeg_command(
    images: list[str],
    output: str,
    music: str,
    duration_per_image: float,
    total_duration: float,
    text: str,
    price: str,
    transition: str,
) -> list[str]:
    """Build the FFmpeg command for slideshow creation."""
    cmd = ["ffmpeg", "-y"]

    has_music = music and Path(music).exists()

    if len(images) == 1:
        # === Single image: use -loop 1 with zoompan ===
        total_duration = max(total_duration, 5.0)  # At least 5s for single image
        frames = int(total_duration * VIDEO_FPS)

        cmd.extend(["-loop", "1", "-i", images[0]])

        if has_music:
            cmd.extend(["-i", music])

        # Zoompan for Ken Burns effect
        vf_parts = [
            f"zoompan=z='min(zoom+0.0015,1.5)':d={frames}"
            f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:fps={VIDEO_FPS}",
            "format=yuv420p",
        ]
    else:
        # === Multiple images: use concat ===
        concat_path = str(TEMP_DIR / "concat.txt")
        with open(concat_path, "w", encoding="utf-8") as f:
            for img in images:
                # FFmpeg needs forward slashes
                safe_path = img.replace("\\", "/")
                f.write(f"file '{safe_path}'\n")
                f.write(f"duration {duration_per_image}\n")
            # Last image listed again for FFmpeg
            safe_path = images[-1].replace("\\", "/")
            f.write(f"file '{safe_path}'\n")

        cmd.extend(["-f", "concat", "-safe", "0", "-i", concat_path])

        if has_music:
            cmd.extend(["-i", music])

        # Video filters
        vf_parts = [
            f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=decrease",
            f"pad={VIDEO_WIDTH}:{VIDEO_HEIGHT}:(ow-iw)/2:(oh-ih)/2:black",
            f"fps={VIDEO_FPS}",
            "format=yuv420p",
        ]

    # Text overlays
    if text:
        safe_text = text.replace("'", "\\'").replace(":", "\\:")
        vf_parts.append(
            f"drawtext=text='{safe_text}'"
            f":fontsize=48:fontcolor=white"
            f":borderw=3:bordercolor=black"
            f":x=(w-text_w)/2:y=h-200"
            f":enable='gte(t,0)'"
        )

    if price:
        safe_price = price.replace("'", "\\'").replace(":", "\\:")
        vf_parts.append(
            f"drawtext=text='{safe_price}'"
            f":fontsize=56:fontcolor=#FF6B35"
            f":borderw=3:bordercolor=black"
            f":x=(w-text_w)/2:y=h-130"
            f":enable='gte(t,0)'"
        )

    cmd.extend(["-vf", ",".join(vf_parts)])

    # Video encoding — optimized for i5 (libx264)
    cmd.extend([
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-t", str(total_duration),
    ])

    # Audio
    if has_music:
        cmd.extend([
            "-c:a", "aac",
            "-b:a", "128k",
            "-shortest",
        ])
    else:
        cmd.extend(["-an"])

    cmd.append(output)
    return cmd


def _pick_random_music() -> str:
    """Pick a random music file from the library."""
    music_files = []
    for ext in ("*.mp3", "*.wav", "*.m4a", "*.ogg"):
        music_files.extend(MUSIC_DIR.rglob(ext))

    if not music_files:
        logger.warning("⚠️ No music files found in music directory")
        return ""

    choice = random.choice(music_files)
    logger.info(f"🎵 Selected music: {choice.name}")
    return str(choice)


async def add_music_to_video(
    video_path: str,
    music_path: str,
    output_path: str = "",
) -> Optional[str]:
    """Add background music to an existing video (e.g., Veo output)."""
    if not output_path:
        output_path = str(
            TEMP_DIR / f"with_music_{Path(video_path).stem}.mp4"
        )

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", music_path,
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "128k",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-shortest",
        output_path,
    ]

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()

    if process.returncode == 0:
        logger.info(f"✅ Music added to video — {output_path}")
        return output_path
    else:
        logger.error(f"❌ Failed to add music: {stderr.decode()[:300]}")
        return None


async def add_text_overlay(
    video_path: str,
    text: str,
    price: str = "",
    output_path: str = "",
) -> Optional[str]:
    """Add text overlay to an existing video (e.g., Veo output)."""
    if not output_path:
        output_path = str(
            TEMP_DIR / f"overlay_{Path(video_path).stem}.mp4"
        )

    vf_parts = []

    if text:
        safe_text = text.replace("'", "\\'")
        vf_parts.append(
            f"drawtext=text='{safe_text}'"
            f":fontsize=48:fontcolor=white"
            f":borderw=3:bordercolor=black"
            f":x=(w-text_w)/2:y=h-200"
        )

    if price:
        safe_price = price.replace("'", "\\'")
        vf_parts.append(
            f"drawtext=text='{safe_price}'"
            f":fontsize=56:fontcolor=#FF6B35"
            f":borderw=3:bordercolor=black"
            f":x=(w-text_w)/2:y=h-130"
        )

    if not vf_parts:
        return video_path

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", ",".join(vf_parts),
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "copy",
        output_path,
    ]

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()

    if process.returncode == 0:
        logger.info(f"✅ Text overlay added — {output_path}")
        return output_path
    else:
        logger.error(f"❌ Failed to add overlay: {stderr.decode()[:300]}")
        return None
