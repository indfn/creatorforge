# Phase 8: Brain Evolution Loop - Context

**Gathered:** 2026-07-13
**Status:** Ready for planning

<domain>
## Phase Boundary

The agent brain automatically evolves its learning weights from real performance data, closing the content strategy feedback loop.

**Depends on:** Phase 7 (analytics data as input for weight updates)

</domain>

<decisions>
## Implementation Decisions

### Weight update algorithm: Ratio-based, capped at ±50%
- **D-01:** For each pillar, compare avg views/CTR/engagement against channel avg — ratio determines weight change
- **D-02:** Cap weight changes at ±50% per cycle to prevent oscillation
- **D-03:** `hook_preferences` updated similarly — if hook type has above-avg CTR, bump that preference
- **D-04:** Updated weights persisted to `channels/{Name}/brain.json`

### Scoring integration: Per-channel brain.json refactor
- **D-05:** `load_brain_context(channel=None)` — if channel provided, read per-channel brain.json; fall back to global
- **D-06:** `score_topic()` gets optional `channel` parameter
- **D-07:** Backward compatible — existing callers without channel continue to use global brain

### Minimum data threshold: Per-pillar skip with clear message
- **D-08:** `update_brain()` counts entries per pillar — pillars with < 3 entries skip weight update
- **D-09:** `performance_patterns` (avg CTR, retention) still updated regardless
- **D-10:** Clear message for each skipped pillar

### Implementation architecture
- **D-11:** `agent_core/analytics/brain_updater.py` — `update_weights()`, `update_hook_preferences()`, `update_performance_patterns()`, `update_brain()` orchestrator
- **D-12:** `update_brain()` calls: load analytics → update weights → update hook preferences → update performance patterns → persist brain.json → return change summary
- **D-13:** `run_scheduled_collection()` (ANALYTICS-03) is a simple CLI-callable function that checks eligible videos and triggers collection — lives in `collector.py`. Not a daemon or background process.
</decisions>

<canonical_refs>
### Phase Requirements
- `.planning/REQUIREMENTS.md` — ANALYTICS-03, 04, 05, 07
- `.planning/ROADMAP.md` — Phase 8 success criteria
- `channels/ChannelA/brain.json` — Reference brain shape
- `agent_core/scoring/engine.py` — Scoring engine (to refactor)

### Existing Implementation
- `agent_core/analytics/brain_updater.py` — Stubs to implement
- `agent_core/analytics/collector.py` — Phase 7 collector (used by run_scheduled_collection)
- `agent_core/scoring/engine.py` — `load_brain_context()`, `score_topic()` — to add channel param
</canonical_refs>

<code_context>
- brain.json has `learning_weights` (4 fields at 1.0), `hook_preferences` (6 fields at 0), `performance_patterns` (avg placeholders)
- Analytics entries have `content_pillar`, `metrics.views`, `metrics.ctr`, `metrics.engagement_rate` 
- Scoring engine reads `agent_core/data/agent-brain.json` (global) — needs per-channel support
- `validate_or_raise` available for brain.json validation
</code_context>

*Phase: 08-brain-evolution-loop*
*Context gathered: 2026-07-13*
