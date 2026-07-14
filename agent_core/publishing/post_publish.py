"""Post-publish YouTube actions — playlist assignment, comment creation, metadata updates,
thumbnail updates.

After a video is uploaded, the creator needs to assign it to playlists,
pin a comment, update title/description/tags/category, or swap the thumbnail
— all from the agent CLI without entering YouTube Studio.

Usage:
    python3 -m agent_core.publishing.post_publish --video-id abc123 \\
        --pin-comment "Check the description for timestamps!"
    python3 -m agent_core.publishing.post_publish --video-id abc123 \\
        --assign-playlist PLxxx...
    python3 -m agent_core.publishing.post_publish --video-id abc123 \\
        --ensure-playlist "Tutorials"
    python3 -m agent_core.publishing.post_publish --video-id abc123 \\
        --update-title "New Title" --update-description "Updated description"
    python3 -m agent_core.publishing.post_publish --video-id abc123 \\
        --update-thumbnail channels/ChannelA/active_production/thumbnail.png
"""

import argparse
import json
import logging
import mimetypes
import re
from pathlib import Path

from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from agent_core.publishing.oauth import get_authenticated_service

logger = logging.getLogger(__name__)

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
        channel: Channel name (e.g. ``"ChannelA"``).

    Returns:
        Path to the ``channel_config.json`` file.
    """
    return _project_root() / "channels" / channel / "channel_config.json"


def _load_channel_config(channel: str) -> dict:
    """Load the per-channel configuration JSON.

    Args:
        channel: Channel name (e.g. ``"ChannelA"``).

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


def _ensure_tags(tags: list[str] | str | None) -> list[str] | None:
    """Normalize tags to a list, splitting a comma-separated string if needed.

    Args:
        tags: A list of tags, a comma-separated string, or ``None``.

    Returns:
        A list of trimmed tag strings, or ``None`` if input was ``None``.
    """
    if tags is None:
        return None
    if isinstance(tags, str):
        return [t.strip() for t in tags.split(",") if t.strip()]
    return tags


def _count_chapter_lines(description: str) -> int:
    """Count YouTube chapter marker lines in a description.

    Detects lines matching ``HH:MM:SS - Title`` or ``MM:SS - Title``.

    Args:
        description: The description text to scan.

    Returns:
        Number of detected chapter marker lines.
    """
    pattern = re.compile(r"^\d{1,2}:\d{2}(?::\d{2})?\s*-\s*.+", re.MULTILINE)
    return len(pattern.findall(description))


# ====== PUBLIC API ======


def assign_to_playlist(channel: str, video_id: str, playlist_id: str) -> bool:
    """Assign a video to an existing YouTube playlist.

    Reads ``channel_config.json`` for a ``playlists`` array to log the
    playlist name if known.  If the playlist ID is not found in config
    a warning is logged but the API call is still attempted — the ID
    might be valid but not yet registered in the config file.

    Args:
        channel: Channel name (e.g. ``"ChannelA"``).
        video_id: The YouTube video ID to assign.
        playlist_id: The YouTube playlist ID to assign to.

    Returns:
        ``True`` if the video was assigned successfully, ``False`` if
        the playlist was not found (404), quota was exceeded (403), or
        another error occurred.
    """
    # Look up playlist name in channel config (defensive, T-06-03-03)
    config = _load_channel_config(channel)
    playlists = config.get("playlists", [])
    matched_entry = next(
        (p for p in playlists if p.get("id") == playlist_id),
        None,
    )
    if matched_entry:
        logger.info(
            "Assigning to playlist '%s' (%s)",
            matched_entry.get("name", "unknown"),
            playlist_id,
        )
    else:
        logger.warning(
            "Playlist ID %s not found in channel config. "
            "The ID may be valid but is not registered in "
            "channel_config.json.  Proceeding with API call.",
            playlist_id,
        )

    try:
        youtube = get_authenticated_service(channel)
        youtube.playlistItems().insert(
            part="snippet",
            body={
                "snippet": {
                    "playlistId": playlist_id,
                    "resourceId": {
                        "kind": "youtube#video",
                        "videoId": video_id,
                    },
                },
            },
        ).execute()
        logger.info("Assigned video %s to playlist %s", video_id, playlist_id)
        return True

    except HttpError as e:
        # T-06-03-04: DoS — don't crash on API errors
        if e.resp.status == 404:
            logger.warning(
                "Playlist %s not found — skip assignment. "
                "Create it with --ensure-playlist.",
                playlist_id,
            )
            return False
        if e.resp.status == 403 and "quotaExceeded" in str(e):
            logger.error(
                "Quota exhausted. Cannot assign to playlist %s.",
                playlist_id,
            )
            return False
        logger.error(
            "Failed to assign video %s to playlist %s: %s",
            video_id,
            playlist_id,
            e,
        )
        return False

    except Exception as e:
        logger.error(
            "Unexpected error assigning video %s to playlist %s: %s",
            video_id,
            playlist_id,
            e,
        )
        return False


def create_playlist(
    channel: str,
    name: str,
    description: str = "",
    privacy: str = "public",
) -> str:
    """Create a new YouTube playlist.

    Args:
        channel: Channel name (e.g. ``"ChannelA"``).
        name: Playlist title.
        description: Optional playlist description (default: ``""``).
        privacy: Privacy status — ``"public"``, ``"unlisted"``, or
            ``"private"`` (default: ``"public"``).

    Returns:
        The new playlist ID string.

    Raises:
        HttpError: If the API call fails.
    """
    youtube = get_authenticated_service(channel)
    result = (
        youtube.playlists()
        .insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title": name,
                    "description": description,
                },
                "status": {
                    "privacyStatus": privacy,
                },
            },
        )
        .execute()
    )
    playlist_id = result["id"]
    logger.info("Created playlist '%s' (id: %s)", name, playlist_id)
    return playlist_id


def pin_comment(channel: str, video_id: str, text: str) -> str:
    """Post a top-level comment on a video and print manual pinning instructions.

    The YouTube Data API does **not** support programmatic comment pinning.
    After creating the comment this function prints instructions for the
    user to manually pin it in YouTube Studio.

    Args:
        channel: Channel name (e.g. ``"ChannelA"``).
        video_id: The YouTube video ID to comment on.
        text: The comment text.

    Returns:
        The comment thread ID string.

    Raises:
        HttpError: If comments are disabled on the video (403).
    """
    youtube = get_authenticated_service(channel)
    result = (
        youtube.commentThreads()
        .insert(
            part="snippet",
            body={
                "snippet": {
                    "videoId": video_id,
                    "topLevelComment": {
                        "snippet": {
                            "textOriginal": text,
                        },
                    },
                },
            },
        )
        .execute()
    )
    comment_id = result["id"]
    logger.info("Comment created on video %s (id: %s)", video_id, comment_id)

    # YouTube API does NOT support programmatic pinning
    logger.warning(
        "YouTube API does not support programmatic comment pinning. "
        "To pin this comment, go to YouTube Studio > Videos > %s "
        "> Comments, find this comment, and click the pin icon.",
        video_id,
    )
    print(f"Comment posted: {text}")
    print(
        f"Pin it manually at YouTube Studio → Comments → "
        f"\"{text}\" → Pin."
    )

    return comment_id


def update_metadata(
    channel: str,
    video_id: str,
    title: str | None = None,
    description: str | None = None,
    tags: list[str] | str | None = None,
    category_id: str | None = None,
) -> bool:
    """Update a video's metadata (title, description, tags, category) post-hoc.

    Uses a READ-MODIFY-WRITE pattern to preserve any fields not being
    updated.  If the description contains chapter marker lines
    (``MM:SS - Title`` or ``HH:MM:SS - Title``) they are counted and
    logged.

    Args:
        channel: Channel name (e.g. ``"ChannelA"``).
        video_id: The YouTube video ID to update.
        title: New title, or ``None`` to keep existing.
        description: New description, or ``None`` to keep existing.
        tags: New tags (list or comma-separated string), or ``None`` to
            keep existing.
        category_id: New category ID (e.g. ``"27"`` for Education), or
            ``None`` to keep existing.

    Returns:
        ``True`` if the update succeeded, ``False`` on error.
    """
    try:
        youtube = get_authenticated_service(channel)

        # Step 1: READ — fetch current snippet
        response = youtube.videos().list(part="snippet", id=video_id).execute()
        if not response.get("items"):
            logger.error("Video %s not found for metadata update", video_id)
            return False

        current = response["items"][0]["snippet"]

        # Step 2: MODIFY — merge provided fields into existing snippet
        merged = dict(current)
        if title is not None:
            merged["title"] = title
        if description is not None:
            merged["description"] = description
            chapter_count = _count_chapter_lines(description)
            if chapter_count > 0:
                logger.info(
                    "Detected %d chapter marker line(s) in description for video %s",
                    chapter_count,
                    video_id,
                )
        if tags is not None:
            merged["tags"] = _ensure_tags(tags)
        if category_id is not None:
            merged["categoryId"] = category_id

        # Step 3: WRITE — send the merged snippet back
        updated_body = {
            "id": video_id,
            "snippet": merged,
        }
        youtube.videos().update(part="snippet", body=updated_body).execute()
        logger.info("Updated metadata for video %s", video_id)
        return True

    except HttpError as e:
        logger.error("Metadata update failed for video %s: %s", video_id, e)
        return False

    except Exception:
        logger.exception(
            "Unexpected error updating metadata for video %s",
            video_id,
        )
        return False


def update_thumbnail(channel: str, video_id: str, thumbnail_path: str) -> bool:
    """Update a video's thumbnail image post-hoc.

    NOTE: This duplicates ``upload_thumbnail`` from ``uploader.py``.
    # TODO: Deduplicate with uploader.upload_thumbnail — post_publish uses
    same MediaFileUpload pattern.

    Resolves the path relative to the project root if not absolute.
    Validates the file exists and has a ``.jpg``, ``.jpeg``, or ``.png``
    extension before passing it to the API (T-06-03-02).

    Args:
        channel: Channel name (e.g. ``"ChannelA"``).
        video_id: The YouTube video ID to update.
        thumbnail_path: Path to the thumbnail image file (relative to
            project root or absolute).

    Returns:
        ``True`` if the thumbnail was updated, ``False`` on error.
    """
    # Resolve path relative to project root (T-06-03-02)
    path = Path(thumbnail_path)
    if not path.is_absolute():
        path = _project_root() / path

    # Validate file exists
    if not path.exists() or not path.is_file():
        logger.error("Thumbnail file not found: %s", path)
        print(f"Error: Thumbnail file not found: {path}")
        return False

    # Validate image extension (T-06-03-02)
    valid_extensions = {".jpg", ".jpeg", ".png"}
    if path.suffix.lower() not in valid_extensions:
        logger.warning(
            "Thumbnail file %s has unsupported extension '%s'. "
            "Expected .jpg, .jpeg, or .png.",
            path,
            path.suffix,
        )
        print(
            f"Warning: Thumbnail should be a JPEG or PNG file. "
            f"Got: {path.suffix}"
        )
        return False

    try:
        youtube = get_authenticated_service(channel)
        mime_type = mimetypes.guess_type(str(path))[0] or "image/jpeg"
        media = MediaFileUpload(str(path), mimetype=mime_type)
        youtube.thumbnails().set(videoId=video_id, media_body=media).execute()
        logger.info("Thumbnail updated for video %s", video_id)
        print(f"Thumbnail updated for video {video_id}")
        return True

    except HttpError as e:
        logger.error("Thumbnail update failed for video %s: %s", video_id, e)
        print(f"Thumbnail update failed: {e}")
        return False

    except Exception as e:
        logger.exception(
            "Unexpected error updating thumbnail for video %s",
            video_id,
        )
        print(f"Thumbnail update failed: unexpected error — {e}")
        return False


# ====== CLI ENTRY POINT ======


def main():
    """CLI entry point for post-publish YouTube actions.

    Parses arguments and dispatches to the appropriate function(s).
    Multiple ``--update-*`` flags are combined into a single call to
    ``update_metadata``.
    """
    parser = argparse.ArgumentParser(
        description="Post-publish YouTube actions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Pin a comment:
  python3 -m agent_core.publishing.post_publish --video-id abc123 \\
      --pin-comment "Check the description for timestamps!"

  # Assign to a playlist:
  python3 -m agent_core.publishing.post_publish --video-id abc123 \\
      --assign-playlist PLxxx...

  # Create a playlist and assign:
  python3 -m agent_core.publishing.post_publish --video-id abc123 \\
      --ensure-playlist "Tutorials"

  # Update metadata (multiple flags can be combined):
  python3 -m agent_core.publishing.post_publish --video-id abc123 \\
      --update-title "New Title" \\
      --update-description "Updated description with chapters\\n\\n00:00 - Intro" \\
      --update-tags "tag1,tag2" \\
      --update-category 27

  # Update thumbnail:
  python3 -m agent_core.publishing.post_publish --video-id abc123 \\
      --update-thumbnail channels/ChannelA/active_production/thumbnail.png
        """,
    )

    parser.add_argument(
        "--channel",
        default="ChannelA",
        help="Channel name (default: ChannelA)",
    )
    parser.add_argument(
        "--video-id",
        required=True,
        help="YouTube video ID",
    )
    parser.add_argument(
        "--pin-comment",
        type=str,
        help="Post a comment and print manual pinning instructions",
    )
    parser.add_argument(
        "--assign-playlist",
        type=str,
        help="Assign video to an existing playlist by ID",
    )
    parser.add_argument(
        "--ensure-playlist",
        type=str,
        help="Create a playlist (by name) and assign the video to it",
    )
    parser.add_argument(
        "--update-title",
        type=str,
        help="Update video title",
    )
    parser.add_argument(
        "--update-description",
        type=str,
        help="Update video description (may include chapter markers)",
    )
    parser.add_argument(
        "--update-tags",
        type=str,
        help="Update video tags (comma-separated)",
    )
    parser.add_argument(
        "--update-category",
        type=str,
        help="Update video category ID (e.g. 27 for Education)",
    )
    parser.add_argument(
        "--update-thumbnail",
        type=str,
        help="Update video thumbnail (path to image file)",
    )

    args = parser.parse_args()

    channel = args.channel
    video_id = args.video_id
    exit_code = 0

    # --pin-comment: post comment + print manual pinning instructions
    if args.pin_comment is not None:
        try:
            comment_id = pin_comment(channel, video_id, args.pin_comment)
            print(f"Comment created (thread id: {comment_id})")
        except HttpError as e:
            logger.error("Failed to post comment: %s", e)
            print(f"Failed to post comment: {e}")
            exit_code = 1

    # --assign-playlist: assign video to existing playlist
    if args.assign_playlist is not None:
        success = assign_to_playlist(channel, video_id, args.assign_playlist)
        if success:
            print(f"Assigned video {video_id} to playlist {args.assign_playlist}")
        else:
            print(f"Failed to assign video to playlist {args.assign_playlist}")
            exit_code = 1

    # --ensure-playlist: create playlist then assign video to it
    if args.ensure_playlist is not None:
        try:
            new_id = create_playlist(channel, args.ensure_playlist)
            print(
                f"Created playlist '{args.ensure_playlist}' "
                f"(id: {new_id})"
            )
            success = assign_to_playlist(channel, video_id, new_id)
            if success:
                print(
                    f"Assigned video {video_id} to new playlist "
                    f"'{args.ensure_playlist}' ({new_id})"
                )
            else:
                print(
                    f"Created playlist but failed to assign video: {new_id}"
                )
                exit_code = 1
        except HttpError as e:
            logger.error("Failed to create playlist: %s", e)
            print(f"Failed to create playlist: {e}")
            exit_code = 1

    # --update-* flags combined into a single update_metadata call
    has_metadata_update = any(
        x is not None
        for x in [
            args.update_title,
            args.update_description,
            args.update_tags,
            args.update_category,
        ]
    )
    if has_metadata_update:
        success = update_metadata(
            channel,
            video_id,
            title=args.update_title,
            description=args.update_description,
            tags=args.update_tags,
            category_id=args.update_category,
        )
        if success:
            updated_fields = []
            if args.update_title is not None:
                updated_fields.append("title")
            if args.update_description is not None:
                updated_fields.append("description")
            if args.update_tags is not None:
                updated_fields.append("tags")
            if args.update_category is not None:
                updated_fields.append("category")
            print(
                f"Metadata updated for video {video_id}: "
                f"{', '.join(updated_fields)}"
            )
        else:
            print(f"Failed to update metadata for video {video_id}")
            exit_code = 1

    # --update-thumbnail
    if args.update_thumbnail is not None:
        success = update_thumbnail(channel, video_id, args.update_thumbnail)
        if success:
            print(f"Thumbnail updated for video {video_id}")
        else:
            print(f"Failed to update thumbnail for video {video_id}")
            exit_code = 1

    exit(exit_code)


if __name__ == "__main__":
    main()
