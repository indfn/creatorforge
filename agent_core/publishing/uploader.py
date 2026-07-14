"""YouTube Data API v3 upload engine.

Uploads rendered videos to a linked YouTube channel.
Supports resumable chunked upload, thumbnail upload, status updates,
quota budget integration, and exponential backoff on server errors.

Usage:
    python3 -m agent_core.publishing.uploader --channel ChannelA
    python3 -m agent_core.publishing.uploader --channel ChannelA --schedule 2026-07-15T14:00:00Z --dry-run
"""

import argparse
import json
import logging
import mimetypes
import random
import time
from pathlib import Path

from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from agent_core.core.quota import QuotaBudget
from agent_core.publishing.oauth import get_authenticated_service

logger = logging.getLogger(__name__)

# ====== CONSTANTS ======

CATEGORY_MAP: dict[str, str] = {
    "Education": "27",
    "Entertainment": "24",
    "Science & Technology": "28",
    "Music": "10",
    "Gaming": "20",
    "News & Politics": "25",
    "Howto & Style": "26",
    "People & Blogs": "22",
    "Sports": "17",
    "Comedy": "23",
    "Film & Animation": "1",
    "Autos & Vehicles": "2",
    "Travel & Events": "19",
    "Nonprofits & Activism": "29",
}

MAX_RETRIES = 5
CHUNK_SIZE = 256 * 1024
RETRYABLE_STATUSES = {500, 502, 503, 504}


# ====== PRIVATE HELPERS ======


def _project_root() -> Path:
    """Resolve the project root directory.

    Returns the parent of ``agent_core/`` — i.e. the repository root.
    Works regardless of the current working directory because it derives
    the path from this module's location on disk.
    """
    return Path(__file__).resolve().parent.parent.parent


def _channel_config_path(channel: str) -> Path:
    """Resolve the per-channel config file path.

    Args:
        channel: Channel name (e.g. "ChannelA").

    Returns:
        Path to the ``channel_config.json`` file.
    """
    return _project_root() / "channels" / channel / "channel_config.json"


def _load_channel_config(channel: str) -> dict:
    """Load the per-channel configuration JSON.

    Args:
        channel: Channel name (e.g. "ChannelA").

    Returns:
        Parsed ``channel_config.json`` dict, or empty dict if the file is
        missing or malformed.
    """
    config_path = _channel_config_path(channel)
    if not config_path.exists():
        logger.warning("Channel config not found: %s", config_path)
        return {}
    try:
        return json.loads(config_path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to parse channel config %s: %s", config_path, e)
        return {}


def _get_defaults(channel: str) -> dict:
    """Read upload defaults from channel config, falling back to sensible defaults.

    Reads both the ``defaults`` section and the ``youtube.upload_defaults``
    section of ``channels/{channel}/channel_config.json``.  Missing keys
    are filled with sensible hardcoded defaults.

    Args:
        channel: Channel name (e.g. "ChannelA").

    Returns:
        A dict with keys: ``privacy``, ``license``, ``embed``, ``comments``,
        ``category``, ``language``, ``visibility``.
    """
    config = _load_channel_config(channel)
    upload_defaults = config.get("youtube", {}).get("upload_defaults", {})
    defaults_section = config.get("defaults", {})

    return {
        "privacy": defaults_section.get(
            "privacy",
            upload_defaults.get("visibility", "private"),
        ),
        "license": defaults_section.get("license", "youtube"),
        "embed": defaults_section.get("embed", True),
        "comments": defaults_section.get("comments", True),
        "category": upload_defaults.get("category", "Education"),
        "language": upload_defaults.get("language", "en"),
        "visibility": upload_defaults.get("visibility", "private"),
    }


def _build_video_body(
    title: str,
    description: str,
    tags: list[str],
    category: str,
    default_language: str,
    privacy: str,
    publish_at: str | None,
    embeddable: bool,
    license_type: str,
    comments_enabled: bool,
) -> dict:
    """Construct the YouTube API video insert request body.

    Args:
        title: Video title.
        description: Video description (may contain chapter markers, etc.).
        tags: List of tag strings.
        category: YouTube category name (e.g. ``"Education"``).
        default_language: Language code (e.g. ``"en"``).
        privacy: Privacy status — ``"public"``, ``"unlisted"``, or ``"private"``.
        publish_at: Optional ISO 8601 publish datetime.
        embeddable: Whether the video can be embedded on other sites.
        license_type: ``"youtube"`` or ``"creativeCommon"``.
        comments_enabled: Whether to allow comments on the video.

    Returns:
        Dict suitable for use as the ``body`` parameter of
        ``videos().insert()``.
    """
    category_id = CATEGORY_MAP.get(category, "27")  # Default to Education

    snippet = {
        "title": title,
        "description": description,
        "tags": tags,
        "categoryId": category_id,
        "defaultLanguage": default_language,
    }

    status = {
        "privacyStatus": privacy,
        "madeForKids": False,
        "selfDeclaredMadeForKids": False,
        "embeddable": embeddable,
        "license": license_type,
    }

    if publish_at:
        status["publishAt"] = publish_at

    if not comments_enabled:
        status["commentRatingDisabled"] = True

    return {
        "snippet": snippet,
        "status": status,
    }


# ====== PUBLIC API ======


def upload_video(
    channel: str,
    video_path: Path,
    thumbnail_path: Path | None = None,
    privacy: str = "private",
    publish_at: str | None = None,
) -> str | None:
    """Upload a video to YouTube via the resumable upload protocol.

    Performs a pre-flight quota check, builds the video body from channel
    config defaults, uploads with 256 KB chunked resumable transfer, retries
    server errors with exponential backoff, and optionally uploads a
    thumbnail on success.

    Args:
        channel: Channel name (e.g. ``"ChannelA"``).
        video_path: Path to the video file to upload.
        thumbnail_path: Optional path to a thumbnail image.
        privacy: Privacy status — ``"public"``, ``"unlisted"``, or ``"private"``.
        publish_at: Optional ISO 8601 datetime string for scheduled publish
            (e.g. ``"2026-07-15T14:00:00Z"``).

    Returns:
        The YouTube video ID string on success, or ``None`` on failure
        (quota exhausted, upload error, etc.).
    """
    try:
        # Validate video file exists (T-06-02)
        video_path = Path(video_path)
        if not video_path.exists() or not video_path.is_file():
            logger.error("Video file not found: %s", video_path)
            print(f"Error: Video file not found: {video_path}")
            return None

        # Load channel config defaults
        defaults = _get_defaults(channel)

        # Build video body
        body = _build_video_body(
            title=video_path.stem,
            description="Video published via CreatorForge",
            tags=[],
            category=defaults.get("category", "Education"),
            default_language=defaults.get("language", "en"),
            privacy=privacy,
            publish_at=publish_at,
            embeddable=defaults.get("embed", True),
            license_type=defaults.get("license", "youtube"),
            comments_enabled=defaults.get("comments", True),
        )

        # YouTube requires scheduled videos to be private
        if publish_at and privacy == "public":
            privacy = "private"
            body["status"]["privacyStatus"] = "private"

        # Pre-flight quota check (T-06-01, D-11)
        quota = QuotaBudget()
        remaining = quota.remaining("youtube_upload")
        print(
            f"Daily upload quota: 6 max. Remaining: {remaining}/6. "
            f"Resets at midnight UTC."
        )

        if not quota.can_consume("youtube_upload", 1):
            print("Remaining upload quota: 0/6 today. Resets at midnight UTC.")
            logger.warning("Upload quota exhausted for channel: %s", channel)
            return None

        # Get authenticated YouTube service
        youtube = get_authenticated_service(channel)

        # Create resumable media upload
        media = MediaFileUpload(str(video_path), chunksize=CHUNK_SIZE, resumable=True)
        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
        )

        # Upload loop with exponential backoff (T-06-04)
        response = None
        attempt = 0

        while response is None and attempt < MAX_RETRIES:
            try:
                status, response = request.next_chunk()
                if status is not None:
                    pct = int(status.progress() * 100) if status.progress() is not None else 0
                    print(f"Upload progress: {pct}%")
            except HttpError as e:
                # Quota exceeded mid-upload (T-06-01)
                if e.resp.status == 403 and "quotaExceeded" in str(e):
                    print("Upload failed: API quota exceeded.")
                    logger.error(
                        "Quota exceeded during upload for channel %s: %s",
                        channel,
                        e,
                    )
                    quota.consume("youtube_upload", 1600)
                    return None

                # Retryable server errors (500/502/503/504)
                if e.resp.status in RETRYABLE_STATUSES and attempt < MAX_RETRIES - 1:
                    sleep_time = (2**attempt) + random.uniform(0, 1)
                    print(
                        f"Server error {e.resp.status}, retrying in "
                        f"{sleep_time:.1f}s (attempt {attempt + 1}/{MAX_RETRIES})"
                    )
                    logger.warning(
                        "Retryable error %s for channel %s, attempt %d/%d",
                        e.resp.status,
                        channel,
                        attempt + 1,
                        MAX_RETRIES,
                    )
                    time.sleep(sleep_time)
                    attempt += 1
                    continue

                # Non-retryable error
                logger.error("Upload failed for channel %s: %s", channel, e)
                print(f"Upload failed: {e}")
                return None

            except Exception as e:
                logger.error(
                    "Unexpected error during upload for channel %s: %s",
                    channel,
                    e,
                )
                print(f"Upload failed: unexpected error — {e}")
                return None

        if response is None:
            logger.error(
                "Upload did not complete after %d attempts for channel %s",
                MAX_RETRIES,
                channel,
            )
            print("Upload failed after all retry attempts.")
            return None

        # Successful upload — consume quota (D-19)
        quota.consume("youtube_upload")
        video_id = response["id"]
        print(f"Upload complete. Video ID: {video_id}")

        # Upload thumbnail if provided
        if thumbnail_path:
            thumb_path = Path(thumbnail_path)
            if thumb_path.exists() and thumb_path.is_file():
                upload_thumbnail(channel, video_id, thumb_path)
            else:
                logger.warning(
                    "Thumbnail file not found: %s, skipping", thumbnail_path
                )
                print(f"Warning: Thumbnail not found at {thumbnail_path}, skipping.")

        return video_id

    except Exception as e:
        logger.exception("Fatal error in upload_video for channel %s", channel)
        print(f"Upload failed: {e}")
        return None


def upload_thumbnail(channel: str, video_id: str, thumbnail_path: Path) -> bool:
    """Upload a thumbnail image for a video.

    Args:
        channel: Channel name (e.g. ``"ChannelA"``).
        video_id: The YouTube video ID to attach the thumbnail to.
        thumbnail_path: Path to the thumbnail image file.

    Returns:
        ``True`` if the thumbnail was uploaded successfully, ``False`` on error.
    """
    try:
        youtube = get_authenticated_service(channel)
        mime_type = mimetypes.guess_type(str(thumbnail_path))[0] or "image/jpeg"
        media = MediaFileUpload(str(thumbnail_path), mimetype=mime_type)
        youtube.thumbnails().set(videoId=video_id, media_body=media).execute()
        print(f"Thumbnail uploaded for video {video_id}")
        return True
    except HttpError as e:
        logger.error("Thumbnail upload failed for video %s: %s", video_id, e)
        print(f"Thumbnail upload failed: {e}")
        return False
    except Exception as e:
        logger.exception(
            "Unexpected error uploading thumbnail for video %s", video_id
        )
        print(f"Thumbnail upload failed: unexpected error — {e}")
        return False


def set_video_status(
    channel: str,
    video_id: str,
    privacy: str = "private",
    publish_at: str | None = None,
) -> bool:
    """Update an uploaded video's privacy status and optional publish schedule.

    Fetches the current video metadata, updates the snippet and status
    fields, then writes the full update back to the API.

    Args:
        channel: Channel name (e.g. ``"ChannelA"``).
        video_id: The YouTube video ID to update.
        privacy: New privacy status — ``"public"``, ``"unlisted"``, or ``"private"``.
        publish_at: Optional ISO 8601 datetime string for scheduled publish.

    Returns:
        ``True`` if the update succeeded, ``False`` on error.
    """
    try:
        youtube = get_authenticated_service(channel)

        # Fetch current video data
        video_response = (
            youtube.videos()
            .list(part="snippet,status", id=video_id)
            .execute()
        )

        if not video_response.get("items"):
            logger.error("Video %s not found for status update", video_id)
            print(f"Error: Video {video_id} not found.")
            return False

        video = video_response["items"][0]
        snippet = video.get("snippet", {})
        status = video.get("status", {})

        # Update status fields
        status["privacyStatus"] = privacy
        if publish_at:
            status["publishAt"] = publish_at
        elif "publishAt" in status:
            del status["publishAt"]

        # Build update body with both snippet and status
        updated_body = {
            "id": video_id,
            "snippet": snippet,
            "status": status,
        }

        youtube.videos().update(
            part="snippet,status",
            body=updated_body,
        ).execute()

        print(f"Video {video_id} status updated to '{privacy}'")
        return True

    except HttpError as e:
        logger.error("Status update failed for video %s: %s", video_id, e)
        print(f"Status update failed: {e}")
        return False
    except Exception as e:
        logger.exception(
            "Unexpected error updating status for video %s", video_id
        )
        print(f"Status update failed: unexpected error — {e}")
        return False


# ====== CLI ENTRY POINT ======


def main():
    """CLI entry point for YouTube video upload.

    Parses arguments, loads channel configuration, displays pre-flight
    quota info, and optionally uploads the video.
    """
    parser = argparse.ArgumentParser(
        description="Upload video to YouTube via resumable protocol",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Upload with auto-generated metadata:
  python3 -m agent_core.publishing.uploader --channel ChannelA

  # Upload with specific video and thumbnail:
  python3 -m agent_core.publishing.uploader --channel ChannelA \\
      --video channels/ChannelA/active_production/render/final_video.mp4 \\
      --thumbnail channels/ChannelA/active_production/thumbnail.png

  # Schedule for later (ISO 8601 datetime):
  python3 -m agent_core.publishing.uploader --channel ChannelA \\
      --schedule 2026-07-15T14:00:00Z

  # Dry-run mode (preview without uploading):
  python3 -m agent_core.publishing.uploader --channel ChannelA --dry-run
        """,
    )

    parser.add_argument(
        "--channel",
        required=True,
        help="Channel name (e.g. ChannelA)",
    )
    parser.add_argument(
        "--video",
        help=(
            "Path to video file "
            "(default: channels/{channel}/active_production/render/final_video.mp4)"
        ),
    )
    parser.add_argument(
        "--thumbnail",
        help="Path to thumbnail image",
    )
    parser.add_argument(
        "--privacy",
        choices=["public", "unlisted", "private"],
        help="Video privacy (default: from channel_config.json or 'private')",
    )
    parser.add_argument(
        "--schedule",
        help="ISO 8601 publish datetime (e.g. 2026-07-15T14:00:00Z)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview generated metadata without uploading",
    )

    args = parser.parse_args()

    # Default video path uses channel name interpolation
    channels_dir = _project_root() / "channels"
    default_video = str(
        channels_dir / args.channel / "active_production" / "render" / "final_video.mp4"
    )
    video_path = args.video or default_video

    # Validate video file exists (T-06-02)
    if not Path(video_path).exists() or not Path(video_path).is_file():
        print(f"Error: Video file not found: {video_path}")
        print(
            "Specify a valid path with --video or ensure the default "
            "render path exists."
        )
        exit(1)

    # Load channel config defaults
    defaults = _get_defaults(args.channel)

    # Resolve privacy: arg > config visibility > config privacy > "private"
    privacy = (
        args.privacy
        or defaults.get("visibility")
        or defaults.get("privacy", "private")
    )

    # Pre-flight quota display (D-11, D-12)
    quota = QuotaBudget()
    remaining = quota.remaining("youtube_upload")
    print(
        f"Daily upload quota: 6 max. Remaining: {remaining}/6. "
        f"Resets at midnight UTC."
    )

    if remaining == 0 and not args.dry_run:
        print("\u26a0 Warning: No remaining upload quota today.")
        proceed = input("Upload quota is exhausted. Continue anyway? (y/N): ")
        if proceed.lower() != "y":
            print("Upload cancelled.")
            exit(0)

    # Build preview metadata
    title = Path(video_path).stem
    description = "Video published via CreatorForge"
    category = defaults.get("category", "Education")

    # Dry-run mode (D-02)
    if args.dry_run:
        print("\n=== DRY RUN \u2014 No upload will occur ===")
        print(f"  Channel:     {args.channel}")
        print(f"  Video:       {video_path}")
        print(f"  Thumbnail:   {args.thumbnail or 'None'}")
        print(f"  Title:       {title}")
        print(f"  Description: {description}")
        print(f"  Category:    {category} (ID: {CATEGORY_MAP.get(category, '27')})")
        print(f"  Privacy:     {privacy}")
        print(f"  Schedule:    {args.schedule or 'None'}")
        print(f"  Tags:        (none \u2014 metadata.py handles SEO)")
        print(f"  Quota:       {remaining}/6 remaining")
        print("=== End dry run ===")
        exit(0)

    # Execute upload
    print(f"\nUploading video for channel: {args.channel}")
    print(f"  File:    {video_path}")
    print(f"  Title:   {title}")
    print(f"  Privacy: {privacy}")
    if args.schedule:
        print(f"  Publish: {args.schedule}")

    video_id = upload_video(
        channel=args.channel,
        video_path=Path(video_path),
        thumbnail_path=Path(args.thumbnail) if args.thumbnail else None,
        privacy=privacy,
        publish_at=args.schedule,
    )

    if video_id:
        print(f"\nUploaded: https://youtube.com/watch?v={video_id}")
    else:
        print("\nUpload failed.")
        exit(1)


if __name__ == "__main__":
    main()
