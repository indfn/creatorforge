---
phase: 08-brain-evolution-loop
plan: 01
subsystem: analytics
tags: [brain-evolution, scheduler, weight-update, hook-preferences, performance-patterns]
key-files:
  created:
    - agent_core/analytics/brain_updater.py
  modified:
    - agent_core/analytics/collector.py
provides: [ANALYTICS-03, ANALYTICS-04, ANALYTICS-07]
requires: [Phase 7 (collector.py, JSONL analytics data)]
metrics:
  duration: 0
  completed_date: "2026-07-15"
tech-stack:
  added: []
  patterns:
    - JSONL file reading with per-line error handling
    - Schema-gated persistence via validate_or_raise
    - Ratio-based weight evolution with capped deltas
---

# Phase 8 Plan 01: Brain Updater & Scheduler — Execution Summary

**One-liner:** Implement the brain evolution loop — `update_weights()`, `update_hook_preferences()`, `update_performance_patterns()`, `update_brain()` orchestrator in `brain_updater.py`, plus `run_scheduled_collection()` in `collector.py` for dual-phase polling.

## Task Completion

| Task | Status | Commit | Key Files |
|------|--------|--------|-----------|
| 1. `run_scheduled_collection(channel) -> int` in collector.py | ✅ Done | `dd36ccd` | `agent_core/analytics/collector.py` |
| 2. Full brain_updater.py with 4 functions | ✅ Done | `f5a4e4f` | `agent_core/analytics/brain_updater.py` |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed pre-existing brain.json schema violations**
- **Found during:** Task 2 verification
- **Issue:** `channels/ChannelA/brain.json` had three schema violations:
  - `$schema` field was an unexpected additional property (`additionalProperties: false` in schema)
  - `identity.tone` was a string `""` but schema requires `array`
  - `monetization.cta_strategy` was a string `""` but schema requires `object`
- **Fix:** Removed `$schema` field, changed `tone` to `[]`, changed `cta_strategy` to empty object `{"default_cta": "", ...}`
- **Files modified:** `channels/ChannelA/brain.json`
- **Note:** brain.json is gitignored (runtime data), so this fix is local-only

## Implementation Details

### Task 1: `run_scheduled_collection(channel) -> int`

Standalone function added to `collector.py` that:
- Discovers published videos via YouTube uploads playlist (same pattern as `collect_recent`)
- Scans a 90-day window for eligible videos
- Skips videos < 1 day old to avoid unnecessary API calls
- Calls `collect_for_video()` + `persist_entry()` for each eligible video
- Returns integer count of videos collected
- Preserves existing `collect_recent()` unchanged

### Task 2: `brain_updater.py` — 4 functions

| Function | Lines | Algorithm |
|----------|-------|-----------|
| `update_weights()` | 85 | Groups by `content_pillar`, computes per-pillar vs channel averages for views/CTR/engagement, caps ratio deltas at ±50% per cycle (D-02), applies to 4 learning weights |
| `update_hook_preferences()` | 65 | Groups by `hook_pattern_used`, computes avg CTR per pattern, scores proportionally on 0-10 scale (D-03) |
| `update_performance_patterns()` | 70 | Computes avg CTR, avg retention_30s, top 5 topics by views, total content count. Always updates regardless of pillar count (D-09) |
| `update_brain()` | 120 | Orchestrator: load JSONL → call all 3 update functions → merge → validate (D-11 gate) → persist brain.json → return change summary |

### Decision Coverage

| Decision | Implementation |
|----------|---------------|
| D-01 | `update_weights`: ratio-based per-pillar vs channel avg |
| D-02 | ±50% cap via `_safe_ratio()` clamping to [0.5, 1.5] |
| D-03 | `update_hook_preferences`: proportional CTR scores 0-10 |
| D-04 | Persisted to `channels/{Name}/brain.json` |
| D-08 | Pillars with < 3 entries skip weight update |
| D-09 | performance_patterns always updated |
| D-10 | Clear log messages per skipped pillar |
| D-11 | `validate_or_raise(brain, 'agent-brain.schema.json')` gates before save |
| D-12 | Orchestrator sequence: load → update → persist |
| D-13 | `run_scheduled_collection()` in collector.py |

### Threat Mitigations

| Threat | Category | Mitigation |
|--------|----------|------------|
| T-08-01 | Tampering | `_read_jsonl_entries()` wraps each JSONL line in try/except |
| T-08-02 | Tampering | `validate_or_raise` runs before every brain.json write |
| T-08-03 | Privilege | Channel name from caller, not filesystem discovery |
| T-08-04 | DoS | All functions handle empty analytics_entries gracefully |
| T-08-05 | Information | Evolution log contains aggregate data only (accepted) |

## Verification Results

- ✅ `python3 -c "from agent_core.analytics.brain_updater import update_brain, update_weights, update_hook_preferences, update_performance_patterns"` — all import
- ✅ `update_brain('ChannelA')` returns dict with all expected keys (weights_updated, hooks_updated, patterns_updated, skipped_pillars, total_videos_analyzed, channel, timestamp)
- ✅ `run_scheduled_collection` imports cleanly alongside `collect_recent`
- ✅ Schema validation passes for updated brain.json
- ✅ Weight caps at [0.5, 1.5] verified against extreme ratio test data
- ✅ Hook preference scores in 0-10 range verified
- ✅ Evolution log appended to brain.json on `update_brain`
- ✅ Empty data test: `update_brain` works when no analytics JSONL files exist
- ⚠️ `ruff check` / `mypy` skipped — linting tools not installed in environment

## Self-Check: PASSED

- [x] `agent_core/analytics/brain_updater.py` exists with 4 complete functions
- [x] `update_weights()` groups by content_pillar, computes ratios, caps at ±50%
- [x] `update_hook_preferences()` groups by hook_pattern_used, computes 0-10 scores
- [x] `update_performance_patterns()` computes avg metrics + top 5 topics
- [x] `update_brain()` orchestrator loads → updates → validates → persists
- [x] `update_brain()` skips pillars with < 3 entries and reports them
- [x] `update_brain()` always updates performance_patterns
- [x] `validate_or_raise` gates before brain.json save
- [x] Evolution log appended with each update cycle
- [x] `run_scheduled_collection(channel)` exists and returns int
- [x] All functions import cleanly
