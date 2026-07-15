"""Retrospective brain evolution loop.

Reads analytics data, computes pattern shifts, and updates the channel's
brain.json with new learning_weights, hook_preferences, and performance_patterns.
Replaces /viral:update-brain as the programmatic backend.

Public Functions:
    update_weights(channel, analytics_entries) -> dict
    update_hook_preferences(channel, analytics_entries) -> dict
    update_performance_patterns(channel, analytics_entries) -> dict
    update_brain(channel) -> dict
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

from agent_core.core.validation import validate_or_raise

logger = logging.getLogger(__name__)


# ====== PRIVATE HELPERS ======


def _project_root() -> Path:
    """Resolve the project root directory (parent of agent_core/)."""
    return Path(__file__).resolve().parent.parent.parent


def _read_jsonl_entries(path: Path) -> list[dict]:
    """Read all JSONL entries from a file, skipping empty lines and malformed JSON.

    Per T-08-01: wraps each line in try/except — malformed JSON lines are
    skipped with WARNING log; one bad line never crashes the full update.
    """
    entries: list[dict] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    logger.warning("Skipping malformed JSONL line in %s", path)
    except FileNotFoundError:
        logger.warning("JSONL file not found: %s", path)
    except Exception as e:
        logger.warning("Error reading JSONL file %s: %s", path, e)
    return entries


def _load_analytics_entries(channel: str) -> list[dict]:
    """Load ALL analytics entries for a channel from its JSONL files.

    Scans channels/{channel}/data/analytics/{content_id}/*.jsonl
    and returns a flat list of all entry dicts.

    Uses the same path structure as collector.py's persist_entry:
    channels/{channel}/data/analytics/{content_id}/{YYYY-MM-DD}.jsonl

    Args:
        channel: Channel name (e.g. 'ChannelA')

    Returns:
        List of analytics entry dicts. Empty list if no data.
    """
    project_root = _project_root()
    analytics_root = project_root / "channels" / channel / "data" / "analytics"
    if not analytics_root.exists():
        logger.info("No analytics data found for channel %s", channel)
        return []

    all_entries: list[dict] = []
    for video_dir in sorted(analytics_root.iterdir()):
        if not video_dir.is_dir():
            continue
        for jsonl_file in sorted(video_dir.glob("*.jsonl")):
            all_entries.extend(_read_jsonl_entries(jsonl_file))

    logger.info(
        "Loaded %d analytics entries for channel %s",
        len(all_entries), channel,
    )
    return all_entries


# ====== PUBLIC API ======


def update_weights(channel: str, analytics_entries: list[dict]) -> dict:
    """Update learning weights based on content pillar performance data.

    Groups entries by content_pillar, calculates per-pillar performance vs
    channel average, and derives weight deltas capped at ±50% per cycle (D-02).

    Per D-01:
      - For each pillar, compare avg views/CTR/engagement against channel avg
      - Ratio determines weight change
    Per D-02:
      - Cap weight changes at ±50% per cycle to prevent oscillation
    Per D-08:
      - Pillars with < 3 entries skip weight update

    Args:
        channel: Channel name (unused in computation, used for logging context).
        analytics_entries: List of analytics entry dicts.

    Returns:
        Updated learning_weights dict matching agent-brain.schema.json.
    """
    if not analytics_entries:
        logger.info(
            "No analytics entries for channel %s — returning default weights",
            channel,
        )
        return {
            "icp_relevance": 1.0,
            "timeliness": 1.0,
            "content_gap": 1.0,
            "proof_potential": 1.0,
        }

    # ---- Group by content_pillar ----
    pillar_entries: dict[str, list[dict]] = {}
    for entry in analytics_entries:
        pillar = entry.get("content_pillar")
        if not pillar:
            continue
        if pillar not in pillar_entries:
            pillar_entries[pillar] = []
        pillar_entries[pillar].append(entry)

    if not pillar_entries:
        logger.info(
            "No content_pillar data in analytics entries — returning default weights",
        )
        return {
            "icp_relevance": 1.0,
            "timeliness": 1.0,
            "content_gap": 1.0,
            "proof_potential": 1.0,
        }

    # ---- Channel-level averages ----
    def _avg_metric(entries: list[dict], metric: str) -> float:
        values = [
            e["metrics"][metric]
            for e in entries
            if e.get("metrics") and e["metrics"].get(metric) is not None
        ]
        return mean(values) if values else 0.0

    channel_avg_views = _avg_metric(analytics_entries, "views")
    channel_avg_ctr = _avg_metric(analytics_entries, "ctr")
    channel_avg_engagement = _avg_metric(analytics_entries, "engagement_rate")

    # ---- Per-pillar ratios with ±50% cap ----
    def _safe_ratio(pillar_avg: float, channel_avg: float) -> float:
        if channel_avg == 0:
            return 1.0  # No signal — neutral
        raw_ratio = pillar_avg / channel_avg
        return max(0.5, min(1.5, raw_ratio))  # Cap at [0.5, 1.5] per D-02

    pillar_deltas: list[dict] = []

    for pillar_name, entries in pillar_entries.items():
        if len(entries) < 3:
            logger.info(
                "Pillar '%s': only %d entries (< 3), skipping weight update (D-08)",
                pillar_name, len(entries),
            )
            continue

        pillar_avg_views = _avg_metric(entries, "views")
        pillar_avg_ctr = _avg_metric(entries, "ctr")
        pillar_avg_engagement = _avg_metric(entries, "engagement_rate")

        pillar_deltas.append({
            "views_ratio": _safe_ratio(pillar_avg_views, channel_avg_views),
            "ctr_ratio": _safe_ratio(pillar_avg_ctr, channel_avg_ctr),
            "engagement_ratio": _safe_ratio(pillar_avg_engagement, channel_avg_engagement),
        })

    if not pillar_deltas:
        logger.info("No pillars with >= 3 entries — returning default weights")
        return {
            "icp_relevance": 1.0,
            "timeliness": 1.0,
            "content_gap": 1.0,
            "proof_potential": 1.0,
        }

    # ---- Average deltas across qualified pillars ----
    avg_views_ratio = mean(d["views_ratio"] for d in pillar_deltas)
    avg_ctr_ratio = mean(d["ctr_ratio"] for d in pillar_deltas)
    avg_engagement_ratio = mean(d["engagement_ratio"] for d in pillar_deltas)
    avg_composite = mean([avg_views_ratio, avg_ctr_ratio, avg_engagement_ratio])

    # ---- Apply to weights (mapping: metric → weight type) ----
    def _apply_delta(ratio: float) -> float:
        """Convert ratio to weight value: ratio 1.0 = weight 1.0, capped at [0.1, 5.0] per schema."""
        delta = ratio - 1.0
        new_weight = 1.0 + delta
        return max(0.1, min(5.0, new_weight))

    weights = {
        "icp_relevance": _apply_delta(avg_views_ratio),
        "timeliness": _apply_delta(avg_ctr_ratio),
        "content_gap": _apply_delta(avg_composite),
        "proof_potential": _apply_delta(avg_engagement_ratio),
    }

    logger.info(
        "Updated weights for channel %s: icp=%.2f, time=%.2f, gap=%.2f, proof=%.2f "
        "(from %d qualified pillars)",
        channel,
        weights["icp_relevance"], weights["timeliness"],
        weights["content_gap"], weights["proof_potential"],
        len(pillar_deltas),
    )
    return weights


def update_hook_preferences(channel: str, analytics_entries: list[dict]) -> dict:
    """Update hook preference scores based on CTR performance per hook pattern.

    Groups entries by hook_pattern_used, computes avg CTR per pattern,
    and scores proportionally on a 0-10 scale (D-03).

    Per agent-brain.schema.json, hook_preferences contains:
        contradiction, specificity, timeframe_tension, pov_as_advice,
        vulnerable_confession, pattern_interrupt

    Args:
        channel: Channel name (logging context).
        analytics_entries: List of analytics entry dicts.

    Returns:
        Updated hook_preferences dict matching agent-brain.schema.json.
    """
    # Default zeroed preferences (all hook types exist in schema)
    default_prefs = {
        "contradiction": 0,
        "specificity": 0,
        "timeframe_tension": 0,
        "pov_as_advice": 0,
        "vulnerable_confession": 0,
        "pattern_interrupt": 0,
    }

    # Group by hook_pattern_used, collect CTR values
    hook_ctrs: dict[str, list[float]] = {}
    for entry in analytics_entries:
        hook = entry.get("hook_pattern_used")
        if not hook or hook not in default_prefs:
            continue  # Skip entries without a recognized hook pattern
        ctr = entry.get("metrics", {}).get("ctr")
        if ctr is None:
            continue
        if hook not in hook_ctrs:
            hook_ctrs[hook] = []
        hook_ctrs[hook].append(float(ctr))

    if not hook_ctrs:
        logger.info(
            "No hook_pattern_used data for channel %s — returning zeroed preferences",
            channel,
        )
        return dict(default_prefs)

    # Compute avg CTR per hook
    hook_avg_ctr: dict[str, float] = {}
    for hook, ctr_values in hook_ctrs.items():
        hook_avg_ctr[hook] = mean(ctr_values) if ctr_values else 0.0

    # Find max avg CTR for proportional scaling
    max_avg_ctr = max(hook_avg_ctr.values()) if hook_avg_ctr else 0.0

    if max_avg_ctr <= 0:
        return dict(default_prefs)

    # Score proportionally (0-10 scale)
    preferences: dict[str, float] = {}
    for hook in default_prefs:
        avg = hook_avg_ctr.get(hook, 0.0)
        score = round((avg / max_avg_ctr) * 10, 1)
        preferences[hook] = min(score, 10.0)  # Cap at 10 per schema maximum

    logger.info(
        "Updated hook preferences for channel %s: %s",
        channel,
        {k: v for k, v in sorted(preferences.items()) if v > 0},
    )
    return preferences


def update_performance_patterns(channel: str, analytics_entries: list[dict]) -> dict:
    """Update aggregate performance patterns from analytics data.

    Computes running averages and identifies top-performing content.
    Always updates regardless of pillar count (D-09).

    Args:
        channel: Channel name (logging context).
        analytics_entries: List of analytics entry dicts.

    Returns:
        Updated performance_patterns dict matching agent-brain.schema.json.
    """
    # Default empty patterns
    default_patterns = {
        "top_performing_topics": [],
        "top_performing_formats": [],
        "audience_growth_drivers": [],
        "avg_ctr": 0,
        "avg_retention_30s": 0,
        "total_content_analyzed": 0,
    }

    if not analytics_entries:
        return dict(default_patterns)

    # ---- Compute avg CTR ----
    ctr_values = [
        float(e["metrics"]["ctr"])
        for e in analytics_entries
        if e.get("metrics") and e["metrics"].get("ctr") is not None
    ]
    avg_ctr = round(mean(ctr_values), 2) if ctr_values else 0.0

    # ---- Compute avg retention_30s ----
    retention_values = [
        float(e["metrics"]["retention_30s"])
        for e in analytics_entries
        if e.get("metrics") and e["metrics"].get("retention_30s") is not None
    ]
    avg_retention = round(mean(retention_values), 2) if retention_values else 0.0

    # ---- Top 5 topics by views ----
    view_counts: dict[str, int] = {}
    for entry in analytics_entries:
        content_id = entry.get("content_id", "")
        views = entry.get("metrics", {}).get("views", 0) or 0
        if content_id:
            # Keep the latest entry per content_id (max views)
            if content_id not in view_counts or views > view_counts[content_id]:
                view_counts[content_id] = views

    sorted_by_views = sorted(
        view_counts.items(), key=lambda x: x[1], reverse=True,
    )
    top_performing_topics = [content_id for content_id, _ in sorted_by_views[:5]]

    # ---- Total content analyzed ----
    # Count unique content_ids (latest entry per video wins)
    unique_content_ids = set()
    for entry in analytics_entries:
        cid = entry.get("content_id")
        if cid:
            unique_content_ids.add(cid)
    total_content_analyzed = len(unique_content_ids)

    patterns = {
        "top_performing_topics": top_performing_topics,
        "top_performing_formats": [],  # Kept as empty list — populated by future analysis
        "audience_growth_drivers": [],  # Kept as empty list — populated by future analysis
        "avg_ctr": avg_ctr,
        "avg_retention_30s": avg_retention,
        "total_content_analyzed": total_content_analyzed,
    }

    logger.info(
        "Updated performance patterns for channel %s: avg_ctr=%.2f%%, avg_retention=%.2f%%, "
        "total_videos=%d",
        channel, avg_ctr, avg_retention, total_content_analyzed,
    )
    return patterns


def update_brain(channel: str) -> dict:
    """Run the full brain evolution cycle for a channel.

    Per D-11/D-12: load analytics → update weights → update hook preferences →
    update performance patterns → persist brain.json → return change summary.

    Per D-08: pillars with < 3 entries skip weight update.
    Per D-09: performance_patterns always updated regardless of pillar count.
    Per D-11: validate_or_raise gates brain.json before save.

    Args:
        channel: Channel name (e.g. 'ChannelA').

    Returns:
        Dict summarizing what changed:
        {
            "weights_updated": bool,
            "hooks_updated": bool,
            "patterns_updated": bool,
            "skipped_pillars": list[str],
            "total_videos_analyzed": int,
            "channel": str,
            "timestamp": str,
        }
    """
    project_root = _project_root()
    brain_path = project_root / "channels" / channel / "brain.json"

    # ---- Load analytics entries ----
    analytics_entries = _load_analytics_entries(channel)

    if not analytics_entries:
        logger.warning("No analytics data for channel %s — brain update skipped", channel)

    # ---- Load current brain.json ----
    if brain_path.exists():
        with open(brain_path, "r", encoding="utf-8") as f:
            brain = json.load(f)
    else:
        logger.warning("brain.json not found for channel %s, creating new brain", channel)
        brain = {}

    # ---- Track skipped pillars (D-08/D-10) ----
    pillar_entries: dict[str, int] = {}
    for entry in analytics_entries:
        pillar = entry.get("content_pillar")
        if pillar:
            pillar_entries[pillar] = pillar_entries.get(pillar, 0) + 1

    skipped_pillars = [
        p for p, count in pillar_entries.items() if count < 3
    ]
    for p in skipped_pillars:
        logger.info(
            "Pillar '%s' has %d entries (< 3), skipping weight update (D-08/D-10)",
            p, pillar_entries[p],
        )

    # ---- Update weights (D-01) ----
    new_weights = update_weights(channel, analytics_entries)
    weights_changed = new_weights != brain.get("learning_weights", {})
    if weights_changed:
        brain["learning_weights"] = new_weights

    # ---- Update hook preferences (D-03) ----
    new_hooks = update_hook_preferences(channel, analytics_entries)
    hooks_changed = new_hooks != brain.get("hook_preferences", {})
    if hooks_changed:
        brain["hook_preferences"] = new_hooks

    # ---- Update performance patterns (always runs, per D-09) ----
    new_patterns = update_performance_patterns(channel, analytics_entries)
    brain["performance_patterns"] = new_patterns
    patterns_updated = bool(analytics_entries)

    # ---- Update metadata ----
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    brain.setdefault("metadata", {})
    brain["metadata"]["updated_at"] = now_iso
    brain["metadata"]["version"] = brain["metadata"].get("version", "0.2.0")

    # Build evolution log entry
    evolution_changes: list[str] = []
    if weights_changed:
        evolution_changes.append(f"weights: {json.dumps(new_weights)}")
    if hooks_changed:
        evolution_changes.append(f"hook_preferences: {json.dumps(new_hooks)}")
    if patterns_updated:
        evolution_changes.append("performance_patterns updated")

    evolution_log = brain["metadata"].setdefault("evolution_log", [])
    evolution_log.append({
        "timestamp": now_iso,
        "reason": f"Brain evolution cycle for channel {channel}",
        "changes": evolution_changes,
    })

    # ---- Validate via validate_or_raise (D-11 gate) ----
    validate_or_raise(brain, "agent-brain.schema.json")

    # ---- Persist brain.json ----
    brain_path.parent.mkdir(parents=True, exist_ok=True)
    with open(brain_path, "w", encoding="utf-8") as f:
        json.dump(brain, f, indent=2, ensure_ascii=False)

    logger.info("Brain updated and persisted for channel %s", channel)

    # ---- Return change summary ----
    total_videos = len({
        e.get("content_id")
        for e in analytics_entries
        if e.get("content_id")
    })

    return {
        "weights_updated": weights_changed,
        "hooks_updated": hooks_changed,
        "patterns_updated": patterns_updated,
        "skipped_pillars": skipped_pillars,
        "total_videos_analyzed": total_videos,
        "channel": channel,
        "timestamp": now_iso,
    }
