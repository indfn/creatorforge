#!/usr/bin/env python3
"""
Fetch per-video YouTube analytics — thin CLI wrapper.

Delegates all API logic to agent_core.analytics.collector.

Usage:
  python scripts/fetch-yt-analytics.py --channel ChannelA --video-id VIDEO_ID
  python scripts/fetch-yt-analytics.py --channel ChannelA --video-id VIDEO_ID --json
  python scripts/fetch-yt-analytics.py --channel ChannelA --recent
  python scripts/fetch-yt-analytics.py --channel ChannelA --recent --days 60
"""

import argparse
import json
import sys
from pathlib import Path

from agent_core.analytics.collector import (
    collect_for_video,
    collect_recent,
    persist_entry,
)

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
ENV_PATH = PROJECT_ROOT / ".env"


def load_env():
    """Load .env file into environment."""
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                import os
                os.environ.setdefault(key.strip(), value.strip())


def _print_entry(entry: dict):
    """Print a human-friendly summary of an analytics entry."""
    metrics = entry.get("metrics", {})

    print(f"Video: {entry.get('content_id', '?')}")
    print(f"Published: {entry.get('published_at', '?')}")
    print(f"Analyzed: {entry.get('analyzed_at', '?')}")
    print(f"Days since publish: {entry.get('days_since_publish', '?')}")

    views = metrics.get("views")
    if isinstance(views, int):
        print(f"Views: {views:,}")
    else:
        print(f"Views: {views}")

    likes = metrics.get("likes")
    if isinstance(likes, int):
        print(f"Likes: {likes:,}")
    else:
        print(f"Likes: {likes}")

    comments = metrics.get("comments")
    if isinstance(comments, int):
        print(f"Comments: {comments:,}")
    else:
        print(f"Comments: {comments}")

    # Deep metrics if available
    impressions = metrics.get("impressions")
    if impressions is not None:
        print(f"Impressions: {impressions:,}")

    ctr = metrics.get("ctr")
    if ctr is not None:
        print(f"CTR: {ctr:.2f}%")

    avg_view_duration = metrics.get("avg_view_duration")
    if avg_view_duration is not None:
        mins = int(avg_view_duration) // 60
        secs = int(avg_view_duration) % 60
        print(f"Avg View Duration: {mins}:{secs:02d}")

    avg_view_percentage = metrics.get("avg_view_percentage")
    if avg_view_percentage is not None:
        print(f"Avg View %: {avg_view_percentage:.1f}%")

    shares = metrics.get("shares")
    if shares is not None:
        print(f"Shares: {shares:,}")

    subs_gained = metrics.get("subscribers_gained")
    if subs_gained is not None:
        print(f"Subs Gained: {subs_gained}")

    engagement_rate = metrics.get("engagement_rate")
    if engagement_rate is not None:
        print(f"Engagement Rate: {engagement_rate:.2f}%")

    print(f"Collection: {entry.get('collection_method', '?')}")


def main():
    parser = argparse.ArgumentParser(
        description="Fetch per-video YouTube analytics via the collector module",
    )
    parser.add_argument(
        "--channel",
        required=True,
        help="Channel name (e.g. ChannelA)",
    )

    # Single video mode
    parser.add_argument(
        "--video-id",
        help="YouTube video ID to collect analytics for",
    )
    parser.add_argument(
        "--days-since-publish",
        type=int,
        default=1,
        help="Days since video was published (default: 1, >= 3 for deep metrics)",
    )

    # Batch mode
    parser.add_argument(
        "--recent",
        action="store_true",
        help="Collect and persist analytics for all videos published in the last N days",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="How many days back to scan (default: 30, used with --recent)",
    )

    # Output
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON (single video mode) or JSON array (recent mode)",
    )

    args = parser.parse_args()
    load_env()

    # Validate mutual exclusivity
    if args.video_id and args.recent:
        print("ERROR: Use --video-id OR --recent, not both.", file=sys.stderr)
        sys.exit(1)

    if not args.video_id and not args.recent:
        print("ERROR: Provide --video-id VIDEO_ID or --recent.", file=sys.stderr)
        sys.exit(1)

    if args.video_id:
        # ---- Single video mode ----
        entry = collect_for_video(
            args.channel,
            args.video_id,
            args.days_since_publish,
        )
        if entry is None:
            print(
                f"No analytics available for video {args.video_id}",
                file=sys.stderr,
            )
            sys.exit(1)

        # Persist
        path = persist_entry(args.channel, entry)

        if args.json:
            print(json.dumps(entry, indent=2))
        else:
            _print_entry(entry)
            print(f"\n[Persisted to {path}]")

    elif args.recent:
        # ---- Batch mode ----
        entries = collect_recent(args.channel, args.days)
        if not entries:
            print(
                f"No analytics collected in the last {args.days} days.",
                file=sys.stderr,
            )
            sys.exit(1)

        if args.json:
            print(json.dumps(entries, indent=2))
        else:
            for entry in entries:
                _print_entry(entry)
                print()
            print(
                f"Collected analytics for {len(entries)} video(s) "
                f"in the last {args.days} days."
            )


if __name__ == "__main__":
    main()
