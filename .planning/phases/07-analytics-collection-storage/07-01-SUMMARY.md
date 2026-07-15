---
phase: 07-analytics-collection-storage
plan: 01
subsystem: analytics
tags: [analytics, youtube, data-api, analytics-api, collector, jsonl, cli]
dependency_graph:
  requires: [Phase 5 (oauth.py), Phase 6 (YouTube publishing)]
  provides: [ANALYTICS-01, ANALYTICS-02, collect_for_video, persist_entry, collect_recent]
  affects: [Phase 8 (scheduling), insights.py, brain_updater.py]
tech-stack:
  added: []
  patterns: [dual-phase polling, JSONL append-only persistence, Analytics API row indexing]
key-files:
  created:
    - agent_core/analytics/collector.py (full rewrite)
  modified:
    - scripts/fetch-yt-analytics.py (refactored to thin CLI)
decisions:
  - "Row index correction: Analytics API response with dimensions='video' has row[0]=video_id, so deep metric indices shifted by 1 vs plan spec"
  - "Removed estimated_minutes_watched from metrics dict (not in schema with additionalProperties: false)"
  - "Sanitized content_id in persist_entry to prevent path traversal (T-07-01)"
  - "Kept load_env() in CLI for backward compatibility"
metrics:
  duration: ~8m
  completed_date: "2026-07-15"
---

# Phase 7 Plan 1: Analytics Collection & Storage Summary

**One-liner:** Dual-phase YouTube analytics collector with per-video basic (24h) + deep (72h) metrics from Data API v3 and Analytics API v2, validated against schema, and persisted as append-only JSONL.

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Analytics API row index mapping off-by-one**
- **Found during:** Task 1 (collect_for_video implementation)
- **Issue:** Plan's row index mapping assumed row[0] was averageViewPercentage for impressions, but with `dimensions="video"`, row[0] is the video dimension value. All indices were shifted by 1 (e.g., `impressions=row[4]` instead of `row[5]`).
- **Fix:** Corrected all row indices to match the actual response layout: row[0]=video_id, row[1]=views, row[2]=estimatedMinutesWatched, row[3]=averageViewDuration, row[4]=averageViewPercentage, row[5]=impressions, row[6]=impressionCtr, row[7]=likes, row[8]=comments, row[9]=shares, row[10]=subscribersGained
- **Files modified:** `agent_core/analytics/collector.py`
- **Commit:** b9de952

**2. [Rule 1 - Bug] estimated_minutes_watched not in schema**
- **Found during:** Task 1
- **Issue:** Plan mapped `estimatedMinutesWatched` API response to `metrics["estimated_minutes_watched"]`, but this field is not in `analytics-entry.schema.json` which has `additionalProperties: false` — would cause validation error.
- **Fix:** Removed the field from the metrics dict since the schema doesn't include it. Deep metrics that ARE in schema (avg_view_duration, avg_view_percentage, impressions, ctr, shares, subscribers_gained, engagement_rate) are all correctly mapped.
- **Files modified:** `agent_core/analytics/collector.py`
- **Commit:** b9de952

**3. [Rule 3 - Blocking] Unused imports and variable from plan template**
- **Found during:** Linting
- **Issue:** `uuid` import unused; `title` variable assigned but never used
- **Fix:** Removed unused import and variable assignment
- **Files modified:** `agent_core/analytics/collector.py`
- **Commit:** b9de952

---

## Threat Surface Mitigations

| Threat ID | Category | Status | Implementation |
|-----------|----------|--------|----------------|
| T-07-01 | Path traversal | Mitigated | `_sanitize_content_id()` strips `/`, `\`, null bytes, and leading dots from content_id |
| T-07-02 | API failure DoS | Mitigated | All API calls wrapped in try/except with graceful fallback, returns None or [] |
| T-07-03 | Credential leaks | Mitigated | Only channel name and video ID logged; HttpError message logged but credentials never exposed |
| T-07-04 | Spoofing | Accepted | Delegated to Phase 5 OAuth module |
| T-07-05 | Schema bypass | Mitigated | `validate_or_raise` runs before `persist_entry` (D-11); ValueError never reaches writer |
| T-07-06 | Repudiation | Mitigated | Append-only JSONL with complete self-contained entries including analyzed_at timestamp |

---

## Implementation Details

### `agent_core/analytics/collector.py` (415 lines)

Three public functions:

1. **`collect_for_video(channel, video_id, days_since_publish=0) -> dict | None`**
   - D-02 gate: returns None if days_since_publish < 1
   - Basic metrics: views, likes, comments via `youtube.videos().list(part="statistics", id=...)`
   - Deep metrics (>= 3 days): impressions, ctr, avg_view_duration, avg_view_percentage, shares, subscribers_gained via `analytics.reports().query(...)`
   - Computes engagement_rate = (likes + comments + shares) / impressions * 100
   - Validates against `analytics-entry.schema.json` before returning
   - Collection method: "mixed" (both APIs) or "youtube_data_api" (basic only)

2. **`persist_entry(channel, entry) -> Path`**
   - Validates via `validate_or_raise` before writing (D-11)
   - Path: `channels/{channel}/data/analytics/{content_id}/{YYYY-MM-DD}.jsonl` (D-09, D-10)
   - Auto-creates directories (D-12)
   - Append-only JSONL with `ensure_ascii=False` for Unicode support

3. **`collect_recent(channel, days=30) -> list[dict]`**
   - Discovers uploads via channel's YouTube playlistItems API
   - Calculates days_since_publish per video
   - Calls collect_for_video + persist_entry for each
   - Paginates through all results (50 per page)

### `scripts/fetch-yt-analytics.py` (158 lines)

Thin CLI wrapper:
- `--channel` required
- Single video mode: `--video-id` + `--days-since-publish`
- Batch mode: `--recent` + `--days`
- `--json` raw output
- Pretty-print display with conditional deep metrics
- Automatic `persist_entry()` after single video collection
- No direct API calls, no `sys.path.insert`, no API key handling

---

## Verification Results

| Check | Result |
|-------|--------|
| `ruff check` on collector.py | ✅ Pass |
| `ruff check` on fetch-yt-analytics.py | ✅ Pass |
| `mypy` on collector.py | ✅ Pass |
| All 3 functions import | ✅ Pass |
| CLI --help shows all flags | ✅ Pass |
| Schema validation (valid entry) | ✅ Pass |
| Schema validation (missing field) | ✅ Correctly fails |
| Path resolution D-09/D-10 | ✅ Correct: `channels/ChannelA/data/analytics/{id}/{date}.jsonl` |
| No sys.path.insert in CLI | ✅ Clean |
| No direct API calls in CLI | ✅ Clean |

---

## Key Decisions

1. **Row index correction:** YouTube Analytics API response with `dimensions="video"` places the dimension value (video_id) at row[0], shifting all metric indices by 1 vs the plan. Corrected all indices.
2. **estimated_minutes_watched excluded:** Not in schema's `metrics` properties with `additionalProperties: false`. Excluded to maintain schema compliance.
3. **Path traversal protection:** `_sanitize_content_id()` strips path separators per T-07-01.
4. **Old CLI functions removed:** `get_oauth_token()`, `fetch_data_api()`, `fetch_analytics_api()`, `fetch_ctr()`, `parse_iso8601_duration()` all migrated to collector module.

---

## Self-Check: PASSED

- [x] `agent_core/analytics/collector.py` exists with 415+ lines (min 180)
- [x] `scripts/fetch-yt-analytics.py` exists as thin CLI (158 lines, min 40)
- [x] Commit b9de952 exists
- [x] Commit c99ecaa exists
- [x] All ruff checks pass
- [x] All mypy checks pass
- [x] Schema validation works for valid and invalid entries
- [x] Path resolution matches D-09 specification
- [x] No stub code remains in collector.py or CLI script
