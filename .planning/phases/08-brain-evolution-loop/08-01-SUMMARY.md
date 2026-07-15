---
phase: 08-brain-evolution-loop
plan: 01
status: READY_FOR_EXECUTION
wave: 1
depends_on: []
subsystem: analytics
tags: [brain-evolution, scheduler, weight-update, hook-preferences, performance-patterns]
provides: [ANALYTICS-03, ANALYTICS-04, ANALYTICS-07, update_brain, run_scheduled_collection]
requires: [Phase 7 (collector.py, JSONL analytics data)]
---

# Phase 8 Plan 01: Brain Updater & Scheduler — READY FOR EXECUTION

**One-liner:** Implement the brain evolution loop — `update_weights()`, `update_hook_preferences()`, `update_performance_patterns()`, `update_brain()` orchestrator in `brain_updater.py`, plus `run_scheduled_collection()` in `collector.py` for dual-phase polling.

## Wave Structure

| Wave | Plan | Tasks | Files |
|------|------|-------|-------|
| 1 | 08-01 | 2 | brain_updater.py, collector.py |

## Plan Summary

### Task 1: `run_scheduled_collection(channel) -> int` (collector.py)
- Discovers published videos via YouTube uploads playlist
- Calculates `days_since_publish` per video
- Calls `collect_for_video()` for eligible videos (gates internally for 24h/72h)
- Returns count of videos collected

### Task 2: `brain_updater.py` — 4 functions
- **`update_weights()`** — Groups by content_pillar, computes channel-vs-pillar ratios, caps deltas at ±50% (D-01, D-02)
- **`update_hook_preferences()`** — Groups by hook_pattern_used, proportional 0-10 CTR-based scores (D-03)
- **`update_performance_patterns()`** — avg CTR, avg retention_30s, top 5 topics, total count (D-09)
- **`update_brain()`** — Orchestrator: load JSONL → update all 3 → merge → validate (D-11) → persist (D-04, D-12) → change summary

## Decision Coverage

| Decision | Implementation |
|----------|---------------|
| D-01 | `update_weights`: ratio-based per-pillar vs channel avg |
| D-02 | ±50% cap via `_safe_ratio()` clamping to [0.5, 1.5] |
| D-03 | `update_hook_preferences`: proportional CTR scores |
| D-04 | Persisted to `channels/{Name}/brain.json` |
| D-08 | Pillars with < 3 entries skip weight update |
| D-09 | performance_patterns always updated |
| D-10 | Clear log messages per skipped pillar |
| D-11 | Functions in `brain_updater.py` |
| D-12 | Orchestrator sequence: load → update → persist |
| D-13 | `run_scheduled_collection()` in collector.py |
