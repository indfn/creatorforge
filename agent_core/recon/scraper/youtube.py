"""
Recon — YouTube competitor scraper using yt-dlp.

Fetches recent videos from YouTube channels, downloads them,
and prepares them for transcription.

Usage:
    from agent_core.recon.scraper.youtube import get_channel_videos, download_video
    videos = get_channel_videos("@Chase-H-AI", max_videos=10)
"""

import json
import subprocess
import time
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Callable

from agent_core.recon.utils.logger import get_logger
from agent_core.recon.skeleton_ripper.cleaning import clean_transcript

logger = get_logger()

DATA_DIR = Path(__file__).parent.parent.parent.parent / "data" / "recon"


def get_channel_videos(
    handle: str,
    max_videos: int = 20,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> List[Dict]:
    """
    Fetch recent video metadata from a YouTube channel using yt-dlp.

    Args:
        handle: YouTube handle (e.g., "@Chase-H-AI") or channel URL
        max_videos: Maximum videos to fetch
        progress_callback: Optional progress callback

    Returns:
        List of video dicts sorted by view count (descending)
    """
    # Normalize handle to URL
    if handle.startswith("@"):
        channel_url = f"https://www.youtube.com/{handle}/videos"
    elif handle.startswith("http"):
        channel_url = handle
    else:
        channel_url = f"https://www.youtube.com/@{handle}/videos"

    logger.info("YOUTUBE", f"Fetching videos from {channel_url}", {"max_videos": max_videos})

    if progress_callback:
        progress_callback(f"Scanning YouTube channel {handle}...")

    try:
        result = subprocess.run(
            [
                "yt-dlp",
                "--flat-playlist",
                "--dump-json",
                "--playlist-end", str(max_videos),
                "--no-warnings",
                "--quiet",
                channel_url,
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            logger.error("YOUTUBE", f"yt-dlp failed for {handle}", {
                "stderr": result.stderr[:300] if result.stderr else None
            })
            return []

        videos = []
        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                video = {
                    "video_id": data.get("id", ""),
                    "url": data.get("url", f"https://www.youtube.com/watch?v={data.get('id', '')}"),
                    "title": data.get("title", ""),
                    "views": data.get("view_count", 0) or 0,
                    "likes": data.get("like_count", 0) or 0,
                    "duration": data.get("duration", 0) or 0,
                    "upload_date": data.get("upload_date", ""),
                    "description": (data.get("description", "") or "")[:200],
                    "channel": handle,
                }
                videos.append(video)
            except json.JSONDecodeError:
                continue

        # Sort by views descending
        videos.sort(key=lambda x: x.get("views", 0), reverse=True)

        logger.info("YOUTUBE", f"Fetched {len(videos)} videos from {handle}", {
            "top_views": videos[0]["views"] if videos else 0
        })

        return videos

    except subprocess.TimeoutExpired:
        logger.error("YOUTUBE", f"yt-dlp timed out for {handle}")
        return []
    except FileNotFoundError:
        logger.error("YOUTUBE", "yt-dlp not found — install with: pip install yt-dlp")
        return []
    except Exception as e:
        logger.error("YOUTUBE", f"Error fetching videos from {handle}", exception=e)
        return []


def download_video(
    video_url: str,
    output_path: Path,
    max_retries: int = 3,
) -> bool:
    """
    Download a YouTube video using yt-dlp.

    Args:
        video_url: YouTube video URL
        output_path: Path for output file
        max_retries: Maximum download attempts

    Returns:
        True if download successful
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    for attempt in range(max_retries):
        try:
            result = subprocess.run(
                [
                    "yt-dlp",
                    "-o", str(output_path),
                    "--quiet",
                    "--no-warnings",
                    "-f", "bestaudio[ext=m4a]/bestaudio/best",
                    video_url,
                ],
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode == 0 and output_path.exists():
                logger.info("YOUTUBE", f"Downloaded video to {output_path}", {
                    "file_size": output_path.stat().st_size
                })
                return True

            logger.warning("YOUTUBE", f"Download attempt {attempt + 1} failed", {
                "stderr": result.stderr[:200] if result.stderr else None
            })

        except subprocess.TimeoutExpired:
            logger.warning("YOUTUBE", f"Download timeout (attempt {attempt + 1})")
        except Exception as e:
            logger.warning("YOUTUBE", f"Download error (attempt {attempt + 1})", {
                "error": str(e)
            })

        if attempt < max_retries - 1:
            time.sleep(2 ** attempt)

    logger.error("YOUTUBE", f"All download attempts failed for {video_url}")
    return False


def get_video_captions(video_id: str, lang: str = "en") -> Optional[str]:
    """
    Extract captions from a YouTube video using yt-dlp.

    Attempts to download auto-generated subtitles in the requested language,
    parse the VTT file, and return cleaned transcript text.

    Args:
        video_id: YouTube video ID (e.g., "dQw4w9WgXcQ")
        lang: Language code for captions (default: "en")

    Returns:
        Cleaned transcript text, or None if captions are unavailable.
        Never raises.
    """
    try:
        result = subprocess.run(
            [
                "yt-dlp",
                "--skip-download",
                "--write-auto-subs",
                "--sub-lang", lang,
                "--sub-format", "vtt",
                "--convert-subs", "vtt",
                "--quiet",
                "--no-warnings",
                "--print", "filename",
                "-o", "%(id)s.%(ext)s",
                f"https://www.youtube.com/watch?v={video_id}",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0 or not result.stdout.strip():
            logger.warning("YOUTUBE",
                           f"No captions available for {video_id} (lang={lang})",
                           {"stderr": result.stderr[:200] if result.stderr else None})
            return None

        vtt_path_str = result.stdout.strip().split("\n")[0]
        vtt_path = Path(vtt_path_str)

        if not vtt_path.exists():
            logger.warning("YOUTUBE", f"VTT file not found: {vtt_path}")
            return None

        raw_vtt = vtt_path.read_text(encoding="utf-8")
        transcript = clean_transcript(raw_vtt, source="youtube_caption")

        # Clean up temp .vtt file
        try:
            vtt_path.unlink()
        except OSError:
            pass

        if transcript and transcript.strip():
            logger.info("YOUTUBE",
                        f"Extracted {len(transcript.split())} words from {video_id} captions")
            return transcript

        logger.warning("YOUTUBE",
                       f"Captions for {video_id} produced empty transcript after cleaning")
        return None

    except FileNotFoundError:
        logger.warning("YOUTUBE", "yt-dlp not found — install with: pip install yt-dlp")
        return None
    except subprocess.TimeoutExpired:
        logger.warning("YOUTUBE",
                       f"yt-dlp timed out fetching captions for {video_id}")
        return None
    except Exception as e:
        logger.warning("YOUTUBE",
                       f"Error fetching captions for {video_id}: {e}")
        return None


def save_channel_data(handle: str, videos: List[Dict]):
    """Save scraped video data to the competitor's data directory."""
    handle_clean = handle.lstrip("@")
    competitor_dir = DATA_DIR / "competitors" / handle_clean
    competitor_dir.mkdir(parents=True, exist_ok=True)

    output = {
        "handle": handle,
        "platform": "youtube",
        "scraped_at": datetime.utcnow().isoformat(),
        "total_videos": len(videos),
        "videos": videos,
    }

    videos_file = competitor_dir / "videos.json"
    with open(videos_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    logger.info("YOUTUBE", f"Saved {len(videos)} videos for {handle} to {videos_file}")
