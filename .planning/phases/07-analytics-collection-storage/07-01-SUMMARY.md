---
phase: 07-analytics-collection-storage
plan: 01
type: execute
status: ready_for_execution
created: 2026-07-15
---

# Plan 07-01 Summary — Analytics Collector

## Objective
Implement the dual-phase analytics collector: `collect_for_video()` (basic at 24h, deep at 72h), `collect_recent()` (batch), `persist_entry()` (JSONL), and refactor `scripts/fetch-yt-analytics.py` into a thin CLI wrapper.

## Requirements Addressed
- **ANALYTICS-01**: 24h-delayed analytics collection per video (YouTube Data + Analytics APIs)
- **ANALYTICS-02**: Persist analytics entries as JSONL with proper schema

## Key Decisions Implemented
- D-01: Both tiers in one module (basic + deep in `collect_for_video`)
- D-04: `days_since_publish` parameter gates metric depth
- D-06: Uses `get_authenticated_service()` from Phase 5 OAuth
- D-07: `fetch-yt-analytics.py` refactored to thin CLI
- D-08/D-11: `validate_or_raise` before every persistence
- D-09/D-10/D-12: JSONL at `channels/{Name}/data/analytics/{video_id}/{YYYY-MM-DD}.jsonl`, append-only, dirs auto-created
- D-13: Three public functions in collector.py

## Files
- `agent_core/analytics/collector.py` — Full implementation (3 tasks)
- `scripts/fetch-yt-analytics.py` — Thin CLI wrapper

## Wave
1 — No dependencies on other Phase 7 plans

## Next Steps
1. Execute this plan
2. Plan 07-02 for ANALYTICS-06 (insights.py aggregate functions) if applicable

## READY FOR EXECUTION
Run: `/gsd-execute-phase 07` or `python3 scripts/fetch-yt-analytics.py --channel ChannelA --video-id VIDEO_ID`
