"""Cross-channel insight aggregation.

Synthesizes patterns across all channels' analytics cycles into
persistent insights. Reads from per-channel analytics JSONL storage,
computes per-metric summary statistics (mean, median, min, max, count),
identifies top/bottom performing content, and produces cross-channel
comparisons so the system can detect which channels and content
strategies are working best.

Public Functions:
    aggregate_channel(channel) -> dict
    aggregate_all() -> dict
"""

import json
import logging
import re
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median

logger = logging.getLogger(__name__)

# =========================================================================
# Private helpers
# =========================================================================

# All numeric metric fields from analytics-entry.schema.json's ``metrics`` object.
NUMERIC_METRICS: list[str] = [
    "views",
    "impressions",
    "likes",
    "comments",
    "shares",
    "saves",
    "subscribers_gained",
    "ctr",
    "avg_view_duration",
    "avg_view_percentage",
    "engagement_rate",
]

# Ranking metrics — used for top/bottom performer identification.
RANKING_METRICS: list[str] = ["views", "ctr", "engagement_rate"]


def _project_root() -> Path:
    """Resolve the project root directory (parent of ``agent_core/``)."""
    return Path(__file__).resolve().parent.parent.parent


def _validate_channel(channel: str) -> None:
    """Validate channel name to prevent path traversal.

    Only allows letters, digits, hyphens, and underscores.

    Raises:
        ValueError: If the channel name contains invalid characters.
    """
    if not re.match(r"^[A-Za-z0-9_-]+$", channel):
        raise ValueError(
            f"Invalid channel name: {channel!r}. "
            "Only letters, numbers, hyphens, underscores allowed."
        )


def _channel_analytics_dir(channel: str) -> Path:
    """Resolve the analytics data directory for a channel.

    Args:
        channel: Validated channel name.

    Returns:
        Path to ``channels/{channel}/data/analytics/``.

    Raises:
        ValueError: If the channel name is invalid.
    """
    _validate_channel(channel)
    return _project_root() / "channels" / channel / "data" / "analytics"


def _read_jsonl_entries(path: Path) -> list[dict]:
    """Read all JSONL lines from a file and return parsed dicts.

    Skips empty lines and logs a warning for lines that cannot be parsed
    as JSON. Entries were validated against the schema on write (D-11), so
    no re-validation is performed here.

    Args:
        path: Path to a ``.jsonl`` file.

    Returns:
        List of parsed entry dicts.
    """
    entries: list[dict] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, ValueError) as e:
        logger.warning("Failed to read JSONL file %s: %s", path, e)
        return []

    for line_no, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue  # skip empty lines
        try:
            entries.append(json.loads(stripped))
        except json.JSONDecodeError as e:
            logger.warning(
                "Skipping malformed JSONL line %d in %s: %s",
                line_no,
                path,
                e,
            )

    return entries


def _compute_metric_stats(values: list[float | int]) -> dict[str, float | int]:
    """Compute summary statistics for a list of numeric values.

    Args:
        values: List of numeric values for one metric across all entries.

    Returns:
        Dict with keys ``mean``, ``median``, ``min``, ``max``, ``count``.
        Returns zero-valued stats for an empty list.
    """
    if not values:
        return {"mean": 0.0, "median": 0.0, "min": 0.0, "max": 0.0, "count": 0}

    return {
        "mean": round(mean(values), 4),
        "median": round(median(values), 4),
        "min": float(min(values)),
        "max": float(max(values)),
        "count": len(values),
    }


def _identify_performers(
    entries: list[tuple[str, dict]],
    metric: str,
    n: int = 3,
    reverse: bool = True,
) -> list[dict]:
    """Identify top or bottom performing entries for a given metric.

    Args:
        entries: List of ``(video_id, entry_dict)`` tuples.
        metric: Metric name to rank by (e.g. ``"views"``).
        n: Number of performers to return (default 3).
        reverse: ``True`` for top (highest first), ``False`` for bottom
            (lowest first).

    Returns:
        List of dicts::
            [{"video_id": str, "value": float}, ...]
    """
    scored: list[tuple[float, str]] = []
    for video_id, entry in entries:
        metrics_dict = entry.get("metrics") or {}
        val = metrics_dict.get(metric)
        if val is not None:
            scored.append((float(val), video_id))

    # Sort by value descending (top) or ascending (bottom)
    scored.sort(key=lambda x: x[0], reverse=reverse)

    return [
        {"video_id": vid, "value": val}
        for val, vid in scored[:n]
    ]


# =========================================================================
# Public API
# =========================================================================


def aggregate_channel(channel: str) -> dict:
    """Aggregate analytics metrics for a single channel.

    Reads all JSONL analytics files from ``channels/{channel}/data/analytics/``,
    deduplicates entries by video ID (keeping the latest), computes per-metric
    summary statistics, and identifies top/bottom performing content.

    Args:
        channel: Channel name (e.g. ``"ChannelA"``).

    Returns:
        Aggregated dict with structure::

            {
                "channel": str,
                "total_videos": int,
                "total_entries": int,
                "metrics": {
                    "<metric_name>": {
                        "mean": float,
                        "median": float,
                        "min": float,
                        "max": float,
                        "count": int
                    },
                    ...
                },
                "top_performers": [
                    {"metric": "views", "rankings": [{"video_id": ..., "value": ...}, ...]},
                    ...
                ],
                "bottom_performers": [...]
            }

        Returns an empty-aggregation dict (all zeros, empty lists) if the
        analytics directory does not exist or contains no data.
    """
    _validate_channel(channel)
    analytics_dir = _channel_analytics_dir(channel)

    if not analytics_dir.is_dir():
        logger.warning("Analytics directory not found for channel %s: %s", channel, analytics_dir)
        return {
            "channel": channel,
            "total_videos": 0,
            "total_entries": 0,
            "metrics": {m: _compute_metric_stats([]) for m in NUMERIC_METRICS},
            "top_performers": [
                {"metric": m, "rankings": []} for m in RANKING_METRICS
            ],
            "bottom_performers": [
                {"metric": m, "rankings": []} for m in RANKING_METRICS
            ],
        }

    # Discover all JSONL files: channels/{channel}/data/analytics/{video_id}/*.jsonl
    jsonl_files = sorted(analytics_dir.glob("*/**/*.jsonl"))

    # Read all entries, tracking video_id from the parent directory name
    all_entries: list[tuple[str, dict]] = []  # (video_id, entry_dict)
    total_lines = 0

    for jsonl_path in jsonl_files:
        # Extract video_id from the parent directory name
        # Path: .../analytics/{video_id}/{YYYY-MM-DD}.jsonl
        video_id = jsonl_path.parent.name
        lines = _read_jsonl_entries(jsonl_path)
        total_lines += len(lines)
        for entry in lines:
            all_entries.append((video_id, entry))

    if not all_entries:
        logger.info("No analytics entries found for channel %s", channel)
        return {
            "channel": channel,
            "total_videos": 0,
            "total_entries": 0,
            "metrics": {m: _compute_metric_stats([]) for m in NUMERIC_METRICS},
            "top_performers": [
                {"metric": m, "rankings": []} for m in RANKING_METRICS
            ],
            "bottom_performers": [
                {"metric": m, "rankings": []} for m in RANKING_METRICS
            ],
        }

    # Deduplicate by content_id (keep last-occurring entry per video)
    # Use an OrderedDict to preserve insertion order while deduplicating
    deduped: dict[str, dict] = OrderedDict()
    for vid, entry in all_entries:
        deduped[vid] = entry

    unique_videos = len(deduped)
    deduped_entries: list[tuple[str, dict]] = list(deduped.items())

    # Compute per-metric stats across deduplicated entries
    metrics_stats: dict[str, dict] = {}
    for metric in NUMERIC_METRICS:
        values: list[float | int] = []
        for _vid, entry in deduped_entries:
            metrics_dict = entry.get("metrics") or {}
            val = metrics_dict.get(metric)
            if val is not None:
                values.append(val)
        metrics_stats[metric] = _compute_metric_stats(values)

    # Top and bottom performers for ranking metrics
    top_performers = [
        {
            "metric": m,
            "rankings": _identify_performers(deduped_entries, m, n=3, reverse=True),
        }
        for m in RANKING_METRICS
    ]
    bottom_performers = [
        {
            "metric": m,
            "rankings": _identify_performers(deduped_entries, m, n=3, reverse=False),
        }
        for m in RANKING_METRICS
    ]

    logger.info(
        "Aggregated %d entries across %d videos for channel %s",
        total_lines,
        unique_videos,
        channel,
    )

    return {
        "channel": channel,
        "total_videos": unique_videos,
        "total_entries": total_lines,
        "metrics": metrics_stats,
        "top_performers": top_performers,
        "bottom_performers": bottom_performers,
    }


def aggregate_all() -> dict:
    """Aggregate analytics across all channels and produce cross-channel comparison.

    Enumerates all directories under ``channels/``, calls
    :func:`aggregate_channel` for each, and computes cross-channel leader
    stats for every numeric metric.

    Returns:
        Combined dict::

            {
                "generated_at": "2026-07-15T12:00:00+00:00",
                "total_channels": int,
                "total_videos_across_channels": int,
                "per_channel": {
                    "ChannelA": { ... aggregate_channel output ... },
                    ...
                },
                "cross_channel_comparison": {
                    "views": {
                        "leader": "ChannelA",
                        "leader_mean": float,
                        "runner_up": "ChannelB",
                        "runner_up_mean": float,
                    },
                    ...
                }
            }

        Returns an empty-structure dict (``total_channels=0``, empty
        ``per_channel``, empty ``cross_channel_comparison``) if the
        ``channels/`` directory does not exist or contains no channels.
    """
    channels_dir = _project_root() / "channels"

    if not channels_dir.is_dir():
        logger.warning("Channels directory not found: %s", channels_dir)
        return _empty_aggregate_all()

    # Enumerate channel directories (skip files, skip hidden dirs)
    channel_names: list[str] = sorted(
        entry.name
        for entry in channels_dir.iterdir()
        if entry.is_dir() and not entry.name.startswith(".")
    )

    if not channel_names:
        return _empty_aggregate_all()

    # Aggregate each channel (gracefully handle errors)
    per_channel: dict[str, dict] = {}
    for name in channel_names:
        try:
            result = aggregate_channel(name)
            per_channel[name] = result
        except ValueError as e:
            logger.warning("Skipping invalid channel directory %s: %s", name, e)
            continue
        except Exception as e:
            logger.warning(
                "Failed to aggregate channel %s (skipping): %s", name, e
            )
            continue

    total_videos_across = sum(
        ch.get("total_videos", 0) for ch in per_channel.values()
    )

    # Cross-channel comparison: for each metric, find the channel with
    # the highest mean value and the runner-up.
    cross: dict[str, dict] = {}
    for metric in NUMERIC_METRICS:
        channel_means: list[tuple[str, float]] = []
        for ch_name, ch_data in per_channel.items():
            mstats = ch_data.get("metrics", {}).get(metric, {})
            mmean = mstats.get("mean", 0.0)
            channel_means.append((ch_name, float(mmean)))

        # Sort by mean descending
        channel_means.sort(key=lambda x: x[1], reverse=True)

        if len(channel_means) >= 2:
            leader, leader_mean = channel_means[0]
            runner_up, runner_up_mean = channel_means[1]
            cross[metric] = {
                "leader": leader,
                "leader_mean": leader_mean,
                "runner_up": runner_up,
                "runner_up_mean": runner_up_mean,
            }
        elif len(channel_means) == 1:
            leader, leader_mean = channel_means[0]
            cross[metric] = {
                "leader": leader,
                "leader_mean": leader_mean,
                "runner_up": "",
                "runner_up_mean": 0.0,
            }
        else:
            cross[metric] = {
                "leader": "",
                "leader_mean": 0.0,
                "runner_up": "",
                "runner_up_mean": 0.0,
            }

    logger.info("Aggregated insights across %d channels", len(per_channel))

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_channels": len(per_channel),
        "total_videos_across_channels": total_videos_across,
        "per_channel": per_channel,
        "cross_channel_comparison": cross,
    }


def _empty_aggregate_all() -> dict:
    """Return an empty aggregate_all structure (no channels exist)."""
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_channels": 0,
        "total_videos_across_channels": 0,
        "per_channel": {},
        "cross_channel_comparison": {
            m: {
                "leader": "",
                "leader_mean": 0.0,
                "runner_up": "",
                "runner_up_mean": 0.0,
            }
            for m in NUMERIC_METRICS
        },
    }
