---
phase: 07-analytics-collection-storage
reviewed: 2026-07-15T12:30:00Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - agent_core/analytics/collector.py
  - agent_core/analytics/insights.py
  - scripts/fetch-yt-analytics.py
  - schemas/analytics-entry.schema.json
findings:
  critical: 0
  warning: 2
  info: 6
  total: 8
status: issues_found
---

# Phase 7: Code Review Report

**Reviewed:** 2026-07-15T12:30:00Z
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Reviewed the analytics collection and storage system across four files: the collector module (415 lines), insights aggregation module (457 lines), CLI wrapper script (202 lines), and the JSON Schema contract (85 lines). The code is generally well-structured with good error handling, clean separation of concerns, and proper schema validation before persistence.

**Key areas addressed per phase requirements:**
- **ANALYTICS-01** (24h/72h dual-phase on-demand collection): Implemented via `days_since_publish` gating — basic metrics at >= 1 day, deep metrics at >= 3 days. Both YouTube Data API v3 and Analytics API v2 integrated.
- **ANALYTICS-02** (JSONL persistence): Path structure follows `channels/{Name}/data/analytics/{video_id}/{YYYY-MM-DD}.jsonl`, append-only writes, schema validation before each write.
- **ANALYTICS-06** (Aggregation): `aggregate_channel()` computes per-metric mean/median/min/max/count with deduplication; `aggregate_all()` provides cross-channel leader/runner-up comparison.

**Two warnings identified:** (1) `NUMERIC_METRICS` in insights.py lists three keys (`retention_30s`, `saves`, `completion_rate`) that the collector never populates — they always report as zero, which can mislead downstream consumers. (2) Single-video CLI mode calls `persist_entry()` without catching `ValueError`, so a schema validation failure crashes the script instead of producing a user-friendly error.

No critical (security) issues found. OAuth token refresh and path traversal sanitization are handled correctly.

## Warnings

### WR-01: Unpopulated metric keys in NUMERIC_METRICS mislead analytics consumers

**Files:**
- `agent_core/analytics/insights.py:30-44`
- `agent_core/analytics/collector.py:168-221`

**Issue:** The `NUMERIC_METRICS` list in `insights.py` includes three keys that `collect_for_video()` never populates:

| Metric key | Schema field | Populated by collector? |
|---|---|---|
| `retention_30s` | `metrics.retention_30s` | ❌ Never set |
| `saves` | `metrics.saves` | ❌ Never set |
| `completion_rate` | `metrics.completion_rate` | ❌ Never set |

The Analytics API query (collector.py:172-176) requests `views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,impressions,impressionCtr,likes,comments,shares,subscribersGained` — notably omitting `retention_30s` and `completion_rate`. The `saves` metric is not available from YouTube Analytics at all.

Because `aggregate_channel()` (insights.py:282-289) iterates all `NUMERIC_METRICS` keys, these three always produce `{"mean": 0.0, "median": 0.0, "min": 0.0, "max": 0.0, "count": 0}` in every channel aggregation result. A downstream consumer (e.g., brain_updater, dashboard) cannot distinguish between "data exists and is 0" vs. "this metric was never collected" vs. "no data available."

**Fix:** Choose one of:
1. Remove `retention_30s`, `saves`, and `completion_rate` from `NUMERIC_METRICS` until the collector actually populates them.
2. Add these metrics to the Analytics API query and row extraction in `collect_for_video()`. Note that `saves` is not a YouTube Analytics metric — it would need a different data source.
3. Add a `None`-aware sentinel in `_compute_metric_stats` (e.g., return `{"mean": None, ...}`) when a metric has zero values across all entries, so consumers can distinguish "not tracked" from "tracked and zero."

### WR-02: Unhandled ValueError in single-video CLI mode causes ungraceful crash

**File:** `scripts/fetch-yt-analytics.py:156-177`

**Issue:** In single-video mode, `persist_entry()` is called without a try/except block:

```python
# Line 171 — no error handling
path = persist_entry(args.channel, entry)
```

`persist_entry()` (collector.py:306) calls `validate_or_raise()` which raises `ValueError` if schema validation fails. In batch mode (`collect_recent` -> `collect_for_video` -> `persist_entry`), the ValueError is caught at collector.py:396 and logged. But the direct call in the CLI has no such protection, so a schema validation failure produces a raw Python traceback instead of a user-friendly error message.

**Trigger scenarios:**
- The API returns a field that violates the schema (e.g., a new YouTube platform value not in the enum)
- The schema file is missing or corrupted
- A malformed video ID produces an invalid `source_url`

**Fix:** Wrap the call in a try/except:

```python
# scripts/fetch-yt-analytics.py line 170-177
try:
    path = persist_entry(args.channel, entry)
except ValueError as e:
    print(f"ERROR: Failed to persist analytics entry: {e}", file=sys.stderr)
    sys.exit(1)

if args.json:
    print(json.dumps(entry, indent=2))
else:
    _print_entry(entry)
    print(f"\n[Persisted to {path}]")
```

## Info

### IN-01: Empty `published_at` produces misleading analytics entries

**File:** `agent_core/analytics/collector.py:142`

```python
published_at_str = snippet.get("publishedAt", "")
```

If the YouTube Data API response lacks `publishedAt` in the snippet (theoretical edge case), `published_at_str` becomes `""`. This empty string propagates into the entry dict as `"published_at": ""`. While the current `jsonschema.validate()` in Python doesn't enforce `format: date-time` by default, an empty string is semantically incorrect for a date field.

**Suggestion:** Default to `None`/omit the key when empty:

```python
published_at_raw = snippet.get("publishedAt") or ""
published_at_str = published_at_raw if published_at_raw else None
```

Then conditionally include it:

```python
entry = {
    ...
    **({"published_at": published_at_str} if published_at_str else {}),
    ...
}
```

### IN-02: `_project_root()` duplicated across modules

**Files:**
- `agent_core/analytics/collector.py:37-44`
- `agent_core/analytics/insights.py:50-52`

Both modules define an identical `_project_root()` helper. The same function also appears in `agent_core/publishing/oauth.py:48-55`. This violates DRY.

**Suggestion:** Extract to a shared utility, e.g. `agent_core/core/paths.py`:

```python
# agent_core/core/paths.py
from pathlib import Path

def project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent
```

Then import from both analytics modules.

### IN-03: YouTube Shorts threshold (180s) is non-standard

**File:** `agent_core/analytics/collector.py:140`

```python
platform = "youtube_longform" if duration_sec > 180 else "youtube_shorts"
```

YouTube officially defines Shorts as <= 60 seconds. Using 180 seconds means videos between 61–180 seconds are classified as `youtube_shorts` when they should be `youtube_longform`. This skews per-platform analytics and could affect downstream winner-detection logic.

**Suggestion:** Change to `duration_sec > 60`:

```python
platform = "youtube_longform" if duration_sec > 60 else "youtube_shorts"
```

### IN-04: `estimatedMinutesWatched` fetched but never stored

**File:** `agent_core/analytics/collector.py:173`

The Analytics API query includes `estimatedMinutesWatched` (line 173), but the row-extraction block (lines 198-209) never accesses `row[2]` which holds this value. The metric is available from the API but silently discarded.

**Suggestion:** Extract and store `estimatedMinutesWatched` if it's useful for downstream analysis, or remove it from the API query to reduce response size.

```python
if len(row) > 2 and row[2] is not None:
    metrics["estimated_minutes_watched"] = int(row[2])
```

If added, also add `estimated_minutes_watched` to the schema's `metrics.properties`.

### IN-05: `import os` inside function body

**File:** `scripts/fetch-yt-analytics.py:37`

```python
def load_env():
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            ...
            import os
            os.environ.setdefault(key.strip(), value.strip())
```

`import os` is inside the function body rather than at the module level. While this works (Python caches the import), it's unconventional and slightly wasteful — the import runs on every `.env` line.

**Suggestion:** Move `import os` to the module top (after line 17).

### IN-06: Redundant `or 0` safety patterns

**File:** `agent_core/analytics/collector.py:212-215`

```python
likes_val = metrics.get("likes", 0) or 0
comments_val = metrics.get("comments", 0) or 0
shares_val = metrics.get("shares", 0) or 0
impressions_val = metrics.get("impressions", 0) or 0
```

`metrics.get(key, 0)` already returns `0` as the default when the key is missing. The additional `or 0` only protects against the value being falsy (e.g., `None`, `False`, `0`). For integer values stored in the metrics dict, a key is either present with a valid integer or absent (falling to default 0). The extra `or 0` is dead logic for the `likes`/`comments` keys (always set from the Data API at lines 147-148) and only marginally defensive for `shares`/`impressions` (which are set only in the deep-metrics branch).

**Suggestion:** Simplify to:

```python
likes_val = metrics.get("likes", 0)
comments_val = metrics.get("comments", 0)
shares_val = metrics.get("shares", 0)
impressions_val = metrics.get("impressions", 0)
```

---

## Summary of status

| Severity | Count | Key issues |
|---|---|---|
| **Critical** | 0 | — |
| **Warning** | 2 | Unpopulated metric keys mislead consumers; unhandled ValueError in CLI mode |
| **Info** | 6 | Code duplication, non-standard Shorts threshold, unused fetch, import style, redundant patterns, edge-case data quality |

All functional requirements (ANALYTICS-01, ANALYTICS-02, ANALYTICS-06) are implemented correctly. Schema validation gates all writes. Path traversal is properly sanitized. OAuth token lifecycle (refresh on expiry) is correctly integrated. No security vulnerabilities found.

---

_Reviewed: 2026-07-15T12:30:00Z_
_Reviewer: gsd-code-reviewer (standard depth)_
_Depth: standard_
