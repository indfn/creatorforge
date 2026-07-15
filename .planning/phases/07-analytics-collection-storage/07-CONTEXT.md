# Phase 7: Analytics Collection & Storage - Context

**Gathered:** 2026-07-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Performance data from published videos is collected in a dual-phase polling loop — basic velocity metrics at 24h, deep behavioral metrics at 72h — validated against schema, and persisted for downstream analysis.

**Depends on:** Phase 6 (needs published videos to collect analytics)

</domain>

<decisions>
## Implementation Decisions

### Polling depth: Both tiers implemented now
- **D-01:** `collect_for_video()` fetches BOTH basic (Data API) and deep (Analytics API) metrics in one module
- **D-02:** Basic metrics (views, likes, comments, shares) available at 24h post-publish
- **D-03:** Deep metrics (CTR, AVD, retention, engagement_rate) available at 72h post-publish
- **D-04:** Polling function accepts `days_since_publish` to gate which metrics to return
- **D-05:** Dual-phase SCHEDULING logic remains in Phase 8 (ANALYTICS-03) — this phase is the FETCH logic

### Architecture: Rewrite as proper module, thin CLI wrapper
- **D-06:** `agent_core/analytics/collector.py` gets full implementation with `get_authenticated_service()` from Phase 5
- **D-07:** `scripts/fetch-yt-analytics.py` refactored to thin CLI wrapper calling the collector module
- **D-08:** Schema validation via `validate_or_raise` before each write

### Storage: Dated JSONL per video
- **D-09:** Path: `channels/{Name}/data/analytics/{video_id}/{YYYY-MM-DD}.jsonl`
- **D-10:** Each collection run appends one JSONL line
- **D-11:** Schema validation via `validate_or_raise(entry, "analytics-entry")` before writing
- **D-12:** Module auto-creates directory structure if missing

### Implementation scope
- **D-13:** `agent_core/analytics/collector.py` — `collect_for_video()`, `collect_recent()`, `persist_entry()`
- **D-14:** `agent_core/analytics/insights.py` — `aggregate_channel()`, `aggregate_all()` with basic stats (mean, median, top/bottom performers)
- **D-15:** `brain_updater.py` — NOT touched (Phase 8 concern)

</decisions>

<canonical_refs>
### Phase Requirements
- `.planning/REQUIREMENTS.md` — ANALYTICS-01, ANALYTICS-02, ANALYTICS-06
- `.planning/ROADMAP.md` — Phase 7 success criteria
- `schemas/analytics-entry.schema.json` — Schema for analytics entries

### Existing Implementation
- `agent_core/analytics/collector.py` — Stubs to implement
- `agent_core/analytics/insights.py` — Stubs to implement
- `scripts/fetch-yt-analytics.py` — Existing script (reference, to be refactored)
- `agent_core/publishing/oauth.py` — OAuth module (get_authenticated_service)
- `agent_core/core/validation.py` — validate_or_raise
</canonical_refs>

<code_context>
- `schemas/analytics-entry.schema.json` — 85 lines, covers all required analytics fields
- `channels/{Name}/data/analytics/` — Target directory for JSONL storage
- `scripts/fetch-yt-analytics.py` uses YouTube Data API (`/videos?part=statistics`) and YouTube Analytics API (`/reports`)
</code_context>

*Phase: 07-analytics-collection-storage*
*Context gathered: 2026-07-13*
