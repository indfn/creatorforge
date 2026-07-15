"""YouTube Analytics API data fetcher.

Pulls per-video performance metrics (views, CTR, retention, engagement)
for the channel's published content. Feeds into brain_updater for evolution.

Dual-phase polling:
  - Basic metrics (views, likes, comments) available at 24h post-publish
  - Deep metrics (CTR, AVD, retention, shares, subs) available at 72h post-publish

Public Functions:
    collect_for_video(channel, video_id, days_since_publish=0) -> dict | None
    collect_recent(channel, days=30) -> list[dict]
    persist_entry(channel, entry) -> Path
"""

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from agent_core.core.validation import validate_or_raise
from agent_core.publishing.oauth import (
    get_authenticated_service,
    get_or_refresh_credentials,
)

logger = logging.getLogger(__name__)


# ====== PRIVATE HELPERS ======


def _project_root() -> Path:
    """Resolve the project root directory.

    Returns the parent of agent_core/ — i.e. the repository root.
    Works regardless of the current working directory because it derives
    the path from this module's location on disk.
    """
    return Path(__file__).resolve().parent.parent.parent


def _parse_iso8601_duration(duration_str: str) -> int:
    """Parse ISO 8601 duration (e.g. 'PT2M45S') to seconds.

    Args:
        duration_str: ISO 8601 duration string.

    Returns:
        Total seconds as int. Returns 0 if parsing fails.
    """
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration_str)
    if not match:
        return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds


def _sanitize_content_id(content_id: str) -> str:
    """Sanitize a content_id for safe filesystem use.

    Strips path separators and parent-directory sequences to prevent
    path traversal (T-07-01).

    Args:
        content_id: Raw content identifier (e.g. YouTube video ID).

    Returns:
        Sanitized string safe for use as a directory name.
    """
    # Replace path separators and null bytes with underscores
    sanitized = content_id.replace("/", "_").replace("\\", "_").replace("\0", "_")
    # Strip leading dots and dashes that could cause hidden/dotfile issues
    sanitized = sanitized.lstrip(".\\/")
    return sanitized if sanitized else "_"


# ====== PUBLIC API ======


def collect_for_video(
    channel: str,
    video_id: str,
    days_since_publish: int = 0,
) -> dict | None:
    """Fetch and return analytics for a single video.

    Per D-02/D-03: basic metrics (views, likes, comments) require >= 1 day
    since publish; deep metrics (CTR, AVD, retention, shares, subs) require
    >= 3 days since publish.

    Args:
        channel: Channel name (e.g. 'ChannelA').
        video_id: YouTube video ID.
        days_since_publish: Days elapsed since video publication.
            0 = skip (data not yet available).
            1-2 = basic metrics only via YouTube Data API v3.
            3+ = basic + deep metrics via YouTube Analytics API v2.

    Returns:
        Analytics entry dict matching analytics-entry.schema.json, or None
        if data is not yet available or an error occurred.
    """
    # ---- Early return gate (D-02): need >= 1 day for any data ----
    if days_since_publish < 1:
        logger.info(
            "Video %s: only %d days since publish, skipping (need >= 1)",
            video_id,
            days_since_publish,
        )
        return None

    try:
        # ---- Get authenticated YouTube Data API service ----
        youtube = get_authenticated_service(channel)

        # ---- Fetch video metadata ----
        response = youtube.videos().list(
            part="statistics,snippet,contentDetails",
            id=video_id,
        ).execute()

        if not response.get("items"):
            logger.warning("Video %s not found via Data API", video_id)
            return None

        item = response["items"][0]
        statistics = item.get("statistics", {})
        snippet = item.get("snippet", {})
        content = item.get("contentDetails", {})

        # Compute format from duration
        duration_sec = _parse_iso8601_duration(content.get("duration", "PT0S"))
        platform = "youtube_longform" if duration_sec > 180 else "youtube_shorts"

        published_at_str = snippet.get("publishedAt", "")

        # ---- Build basic metrics (Data API) ----
        metrics: dict = {
            "views": int(statistics.get("viewCount", 0)),
            "likes": int(statistics.get("likeCount", 0)),
            "comments": int(statistics.get("commentCount", 0)),
        }

        # ---- Determine collection method ----
        collection_method = "youtube_data_api"

        # ---- Deep metrics (Analytics API) - requires >= 3 days (D-03) ----
        if days_since_publish >= 3:
            try:
                creds = get_or_refresh_credentials(channel)
                analytics_service = build(
                    "youtubeAnalytics", "v2",
                    credentials=creds,
                    static_discovery=False,
                )

                # Date range: from publish date to today
                start_date = published_at_str[:10] if published_at_str else "2020-01-01"
                end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

                report = analytics_service.reports().query(
                    ids="channel==MINE",
                    startDate=start_date,
                    endDate=end_date,
                    metrics=(
                        "views,estimatedMinutesWatched,averageViewDuration,"
                        "averageViewPercentage,impressions,impressionCtr,"
                        "likes,comments,shares,subscribersGained"
                    ),
                    dimensions="video",
                    filters=f"video=={video_id}",
                ).execute()

                if report.get("rows"):
                    row = report["rows"][0]
                    # Row layout with dimensions="video":
                    #   row[0]  = video (dimension value)
                    #   row[1]  = views
                    #   row[2]  = estimatedMinutesWatched
                    #   row[3]  = averageViewDuration (seconds)
                    #   row[4]  = averageViewPercentage (%)
                    #   row[5]  = impressions
                    #   row[6]  = impressionCtr (%)
                    #   row[7]  = likes
                    #   row[8]  = comments
                    #   row[9]  = shares
                    #   row[10] = subscribersGained
                    # We already have views/likes/comments from Data API,
                    # but prefer Analytics API values when available for consistency.

                    if len(row) > 5 and row[5] is not None:
                        metrics["impressions"] = int(row[5])
                    if len(row) > 6 and row[6] is not None:
                        metrics["ctr"] = float(row[6])
                    if len(row) > 3 and row[3] is not None:
                        metrics["avg_view_duration"] = float(row[3])
                    if len(row) > 4 and row[4] is not None:
                        metrics["avg_view_percentage"] = float(row[4])
                    if len(row) > 9 and row[9] is not None:
                        metrics["shares"] = int(row[9])
                    if len(row) > 10 and row[10] is not None:
                        metrics["subscribers_gained"] = int(row[10])

                    # Engagement rate = (likes + comments + shares) / impressions * 100
                    likes_val = metrics.get("likes", 0) or 0
                    comments_val = metrics.get("comments", 0) or 0
                    shares_val = metrics.get("shares", 0) or 0
                    impressions_val = metrics.get("impressions", 0) or 0
                    if impressions_val > 0:
                        metrics["engagement_rate"] = round(
                            (likes_val + comments_val + shares_val)
                            / impressions_val
                            * 100,
                            2,
                        )

                collection_method = "mixed"

            except HttpError as e:
                if e.resp.status == 403:
                    logger.warning(
                        "YouTube Analytics API not enabled or not authorized "
                        "for channel %s: %s",
                        channel,
                        e,
                    )
                else:
                    logger.warning(
                        "YouTube Analytics API HTTP error for video %s: %s",
                        video_id,
                        e,
                    )
            except Exception as e:
                logger.warning(
                    "Analytics API query failed for video %s: %s",
                    video_id,
                    e,
                )

        # ---- Build the full entry dict ----
        analyzed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        entry = {
            "id": f"{video_id}_{analyzed_at}",
            "content_id": video_id,
            "platform": platform,
            "published_at": published_at_str,
            "analyzed_at": analyzed_at,
            "days_since_publish": days_since_publish,
            "metrics": metrics,
            "collection_method": collection_method,
            "source_url": f"https://youtube.com/watch?v={video_id}",
        }

        # ---- Validate against schema ----
        try:
            validate_or_raise(entry, "analytics-entry.schema.json")
        except ValueError as e:
            logger.error(
                "Schema validation failed for video %s: %s",
                video_id,
                e,
            )
            return None

        return entry

    except Exception as e:
        logger.error(
            "Failed to collect analytics for video %s on channel %s: %s",
            video_id,
            channel,
            e,
        )
        return None


def persist_entry(channel: str, entry: dict) -> Path:
    """Validate and persist a single analytics entry to JSONL.

    Path: channels/{channel}/data/analytics/{content_id}/{YYYY-MM-DD}.jsonl

    Per D-09, D-10, D-11, D-12:
      - Validates against schema before writing (D-11)
      - Writes one JSONL line per entry (D-10)
      - Auto-creates directory (D-12)
      - Append-only, never overwrites (D-10)

    Args:
        channel: Channel name (e.g. 'ChannelA').
        entry: Analytics entry dict matching analytics-entry.schema.json.

    Returns:
        Path to the written JSONL file.

    Raises:
        ValueError: If entry fails schema validation.
    """
    # Validate entry first (D-11)
    validate_or_raise(entry, "analytics-entry.schema.json")

    # Resolve path (D-09)
    content_id = _sanitize_content_id(entry["content_id"])
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    project_root = _project_root()
    jsonl_dir = project_root / "channels" / channel / "data" / "analytics" / content_id
    jsonl_path = jsonl_dir / f"{today}.jsonl"

    # Auto-create directory (D-12)
    jsonl_dir.mkdir(parents=True, exist_ok=True)

    # Append one JSONL line (D-10)
    with open(jsonl_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")

    logger.info("Persisted analytics entry to %s", jsonl_path)
    return jsonl_path


def _get_uploads_playlist_id(youtube) -> str | None:
    """Get the authenticated channel's upload playlist ID.

    Shared helper to avoid duplicate uploads playlist fetching between
    collect_recent() and run_scheduled_collection() (IN-04).

    Args:
        youtube: Authenticated YouTube API service instance.

    Returns:
        Uploads playlist ID string, or None if not found.
    """
    try:
        channel_response = youtube.channels().list(
            part="contentDetails",
            mine=True,
        ).execute()
        if not channel_response.get("items"):
            return None
        return channel_response["items"][0][
            "contentDetails"
        ]["relatedPlaylists"]["uploads"]
    except Exception:
        return None


def collect_recent(channel: str, days: int = 30) -> list[dict]:
    """Collect and persist analytics for all videos published in the last N days.

    Discovers videos via the channel's YouTube uploads playlist, calculates
    days_since_publish for each, calls collect_for_video(), and persists
    each entry via persist_entry().

    Args:
        channel: Channel name (e.g. 'ChannelA').
        days: How many days back to scan for published videos (default 30).

    Returns:
        List of collected analytics entry dicts. Empty list on failure or
        if no videos found.
    """
    entries: list[dict] = []

    try:
        # Get authenticated service
        youtube = get_authenticated_service(channel)

        # Get the channel's upload playlist ID
        uploads_playlist_id = _get_uploads_playlist_id(youtube)
        if not uploads_playlist_id:
            logger.warning("No upload playlist found for %s", channel)
            return []

        # Fetch uploads via playlistItems
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=days)
        next_page_token: str | None = None

        while True:
            request_params = {
                "part": "snippet,contentDetails",
                "playlistId": uploads_playlist_id,
                "maxResults": 50,
            }
            if next_page_token:
                request_params["pageToken"] = next_page_token

            playlist_response = youtube.playlistItems().list(
                **request_params
            ).execute()

            for item in playlist_response.get("items", []):
                published_at_str = item["snippet"]["publishedAt"]
                published_dt = datetime.fromisoformat(
                    published_at_str.replace("Z", "+00:00")
                )

                if published_dt < cutoff:
                    continue  # Skip videos older than `days`

                video_id = item["snippet"]["resourceId"]["videoId"]
                days_since_publish = (now - published_dt).days

                entry = collect_for_video(channel, video_id, days_since_publish)
                if entry:
                    try:
                        persist_entry(channel, entry)
                        entries.append(entry)
                    except ValueError as e:
                        logger.error(
                            "Failed to persist entry for video %s: %s",
                            video_id,
                            e,
                        )

            next_page_token = playlist_response.get("nextPageToken")
            if not next_page_token:
                break

    except Exception as e:
        logger.error(
            "Failed to collect recent analytics for channel %s: %s",
            channel,
            e,
        )
        return []

    return entries


def run_scheduled_collection(channel: str) -> int:
    """Dual-phase polling scheduler — checks all published videos and collects
    analytics for those meeting the 24h (basic) or 72h+ (deep) thresholds.

    Per D-13 / ANALYTICS-03: the scheduler discovers all published videos via
    the uploads playlist, calculates days_since_publish, and triggers collection
    at two phases:
      - Phase 1 (24h): basic public metrics (views, likes, comments) — pick up
        videos with days_since_publish >= 1 that haven't been collected yet
      - Phase 2 (72h): deep metrics (CTR, AVD, retention) — pick up videos with
        days_since_publish >= 3

    The actual gating by days_since_publish is handled by collect_for_video().
    This function provides the scheduling loop.

    Args:
        channel: Channel name (e.g. 'ChannelA').

    Returns:
        Number of videos successfully collected (could be 0).
    """
    count = 0

    try:
        youtube = get_authenticated_service(channel)

        # Get the channel's upload playlist ID
        uploads_playlist_id = _get_uploads_playlist_id(youtube)
        if not uploads_playlist_id:
            logger.warning("No upload playlist found for %s", channel)
            return 0

        now = datetime.now(timezone.utc)
        scan_window_days = 90
        next_page_token: str | None = None
        seen_video_ids: set[str] = set()

        while True:
            request_params = {
                "part": "snippet,contentDetails",
                "playlistId": uploads_playlist_id,
                "maxResults": 50,
            }
            if next_page_token:
                request_params["pageToken"] = next_page_token

            playlist_response = youtube.playlistItems().list(
                **request_params
            ).execute()

            for item in playlist_response.get("items", []):
                published_at_str = item["snippet"]["publishedAt"]
                published_dt = datetime.fromisoformat(
                    published_at_str.replace("Z", "+00:00")
                )

                # Skip videos older than scan window
                if (now - published_dt).days > scan_window_days:
                    continue

                video_id = item["snippet"]["resourceId"]["videoId"]
                if video_id in seen_video_ids:
                    continue
                seen_video_ids.add(video_id)

                days_since_publish = (now - published_dt).days

                # Skip videos less than 1 day old (data not available)
                if days_since_publish < 1:
                    continue

                entry = collect_for_video(channel, video_id, days_since_publish)
                if entry:
                    try:
                        persist_entry(channel, entry)
                        count += 1
                    except ValueError as e:
                        logger.error(
                            "Failed to persist entry for video %s: %s",
                            video_id, e,
                        )

            next_page_token = playlist_response.get("nextPageToken")
            if not next_page_token:
                break

    except Exception as e:
        logger.error(
            "Scheduled collection failed for channel %s: %s",
            channel, e,
        )
        return 0

    logger.info(
        "Scheduled collection: collected %d video(s) for channel %s",
        count, channel,
    )
    return count
