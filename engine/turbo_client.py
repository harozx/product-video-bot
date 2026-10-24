"""
MoneyPrinterTurbo API Client.
Gọi API tạo video từ auto-content → MoneyPrinterTurbo (port 8080).
Hỗ trợ 2 mode:
  1. Video từ topic (stock footage + voice + subtitle)
  2. Video từ ảnh sản phẩm (upload ảnh → voice + subtitle)
"""

import asyncio
import logging
import shutil
from pathlib import Path
from typing import Optional

import httpx

from config import TURBO_BASE_URL

logger = logging.getLogger(__name__)

POLL_INTERVAL = 5  # seconds
MAX_WAIT_TIME = 300  # 5 minutes max


async def create_video_from_topic(
    subject: str,
    language: str = "vi-VN",
    voice_name: str = "vi-VN-HoaiMyNeural",
    video_script: str = "",
    video_aspect: str = "9:16",
    video_count: int = 1,
    subtitle_enabled: bool = True,
) -> Optional[str]:
    """
    Tạo video bằng MoneyPrinterTurbo — stock footage + voice + subtitle.
    Dùng khi ảnh sản phẩm xấu hoặc muốn video style "faceless".
    
    Returns:
        Path to final video file, or None if failed.
    """
    payload = {
        "video_subject": subject,
        "video_script": video_script,
        "video_aspect": video_aspect,
        "video_count": video_count,
        "video_language": language,
        "voice_name": voice_name,
        "voice_volume": 1.0,
        "bgm_type": "random",
        "bgm_volume": 0.2,
        "subtitle_enabled": subtitle_enabled,
        "subtitle_position": "bottom",
        "text_fore_color": "#FFFFFF",
        "font_size": 60,
        "stroke_color": "#000000",
        "stroke_width": 1.5,
        "n_threads": 2,
        "paragraph_number": 1,
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{TURBO_BASE_URL}/api/v1/videos", json=payload)
            resp.raise_for_status()
            data = resp.json()

        task_id = data.get("data", {}).get("task_id")
        if not task_id:
            logger.error(f"No task_id in response: {data}")
            return None

        logger.info(f"🎬 Turbo task created: {task_id}")
        return await _wait_for_task(task_id)

    except httpx.ConnectError:
        logger.error("❌ MoneyPrinterTurbo không chạy! Chạy: cd d:\\MoneyPrinterTurbo && python main.py")
        return None
    except Exception as e:
        logger.error(f"❌ Turbo API error: {e}")
        return None


async def create_video_with_images(
    subject: str,
    image_paths: list[str],
    video_script: str = "",
    language: str = "vi-VN",
    voice_name: str = "vi-VN-HoaiMyNeural",
    video_aspect: str = "9:16",
    subtitle_enabled: bool = True,
) -> Optional[str]:
    """
    Tạo video bằng MoneyPrinterTurbo — dùng ẢNH SẢN PHẨM + voice + subtitle.
    Upload ảnh SP vào local_videos → Turbo dùng làm material.

    Returns:
        Path to final video file, or None if failed.
    """
    # Upload images to Turbo's local_videos directory
    try:
        uploaded_files = []
        async with httpx.AsyncClient(timeout=60) as client:
            for img_path in image_paths:
                with open(img_path, "rb") as f:
                    files = {"file": (Path(img_path).name, f, "image/jpeg")}
                    resp = await client.post(
                        f"{TURBO_BASE_URL}/api/v1/video_materials",
                        files=files,
                    )
                    if resp.status_code == 200:
                        uploaded_files.append(resp.json().get("data", {}).get("file", ""))
                        logger.info(f"✅ Uploaded: {Path(img_path).name}")

        if not uploaded_files:
            logger.error("No images uploaded successfully")
            return None

        # Create video with uploaded materials
        materials = [{"url": f, "duration": 5} for f in uploaded_files]
        payload = {
            "video_subject": subject,
            "video_script": video_script,
            "video_aspect": video_aspect,
            "video_count": 1,
            "video_source": "local",
            "video_materials": materials,
            "video_language": language,
            "voice_name": voice_name,
            "voice_volume": 1.0,
            "bgm_type": "random",
            "bgm_volume": 0.2,
            "subtitle_enabled": subtitle_enabled,
            "subtitle_position": "bottom",
            "text_fore_color": "#FFFFFF",
            "font_size": 60,
            "stroke_color": "#000000",
            "stroke_width": 1.5,
            "n_threads": 2,
            "paragraph_number": 1,
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{TURBO_BASE_URL}/api/v1/videos", json=payload)
            resp.raise_for_status()
            data = resp.json()

        task_id = data.get("data", {}).get("task_id")
        if not task_id:
            return None

        logger.info(f"🎬 Turbo task (with images) created: {task_id}")
        return await _wait_for_task(task_id)

    except httpx.ConnectError:
        logger.error("❌ MoneyPrinterTurbo không chạy!")
        return None
    except Exception as e:
        logger.error(f"❌ Turbo API error: {e}")
        return None


async def _wait_for_task(task_id: str) -> Optional[str]:
    """Poll task status until complete or timeout."""
    elapsed = 0
    async with httpx.AsyncClient(timeout=30) as client:
        while elapsed < MAX_WAIT_TIME:
            await asyncio.sleep(POLL_INTERVAL)
            elapsed += POLL_INTERVAL

            try:
                resp = await client.get(f"{TURBO_BASE_URL}/api/v1/tasks/{task_id}")
                if resp.status_code != 200:
                    continue

                task_data = resp.json().get("data", {})
                state = task_data.get("state", 0)
                progress = task_data.get("progress", 0)

                logger.info(f"⏳ Task {task_id}: state={state}, progress={progress}%")

                # state: 1=processing, 2=done, 3=failed
                if state == 2:  # Completed
                    videos = task_data.get("videos", [])
                    if videos:
                        video_url = videos[0]
                        # Download video to local temp
                        return await _download_video(client, video_url, task_id)
                    return None

                elif state == 3:  # Failed
                    logger.error(f"❌ Task {task_id} failed")
                    return None

            except Exception as e:
                logger.warning(f"Poll error: {e}")

    logger.error(f"⏰ Task {task_id} timeout after {MAX_WAIT_TIME}s")
    return None


async def _download_video(client: httpx.AsyncClient, video_url: str, task_id: str) -> Optional[str]:
    """Download the generated video from Turbo server."""
    try:
        # Video might be a URL or a file path
        if video_url.startswith("http"):
            download_url = video_url
        else:
            # It's a local path reference — construct download URL
            # e.g. /tasks/xxx/final-1.mp4
            path_part = video_url.split("/tasks/")[-1] if "/tasks/" in video_url else f"{task_id}/final-1.mp4"
            download_url = f"{TURBO_BASE_URL}/api/v1/download/{path_part}"

        resp = await client.get(download_url, timeout=120)
        if resp.status_code != 200:
            # Try direct file path approach
            turbo_tasks = Path("d:/MoneyPrinterTurbo/storage/tasks")
            local_video = turbo_tasks / task_id / "final-1.mp4"
            if local_video.exists():
                # Copy to auto-content temp
                dest = Path("d:/auto-content/temp") / f"turbo_{task_id}.mp4"
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(local_video), str(dest))
                logger.info(f"✅ Video copied: {dest}")
                return str(dest)
            return None

        # Save downloaded video
        dest = Path("d:/auto-content/temp") / f"turbo_{task_id}.mp4"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(resp.content)
        logger.info(f"✅ Video downloaded: {dest}")
        return str(dest)

    except Exception as e:
        # Fallback: try local file directly
        logger.warning(f"Download failed: {e}, trying local path...")
        local_video = Path(f"d:/MoneyPrinterTurbo/storage/tasks/{task_id}/final-1.mp4")
        if local_video.exists():
            dest = Path("d:/auto-content/temp") / f"turbo_{task_id}.mp4"
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(local_video), str(dest))
            return str(dest)
        return None


async def check_turbo_health() -> bool:
    """Check if MoneyPrinterTurbo API is running."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{TURBO_BASE_URL}/docs")
            return resp.status_code == 200
    except Exception:
        return False
