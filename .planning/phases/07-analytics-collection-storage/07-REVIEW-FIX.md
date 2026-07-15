---
phase: 07-analytics-collection-storage
fixed_at: 2026-07-15T14:00:00Z
review_path: .planning/phases/07-analytics-collection-storage/07-REVIEW.md
iteration: 1
findings_in_scope: 2
fixed: 2
skipped: 0
status: all_fixed
---

# Phase 7: Code Review Fix Report

**Fixed at:** 2026-07-15T14:00:00Z
**Source review:** `.planning/phases/07-analytics-collection-storage/07-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 2
- Fixed: 2
- Skipped: 0

## Fixed Issues

### WR-01: Unpopulated metric keys in NUMERIC_METRICS mislead analytics consumers

**Files modified:** `agent_core/analytics/insights.py`
**Commit:** `f43b892`
**Applied fix:** Removed `retention_30s` and `completion_rate` from the `NUMERIC_METRICS` list in `insights.py` since the collector (`collect_for_video()`) never populates them. Kept `saves` as it is part of the schema and may be populated from non-YouTube sources (e.g., Instagram). This prevents aggregation results from always reporting 0.0 for these metrics, which was misleading downstream consumers who couldn't distinguish between "data exists and is zero" vs. "metric was never collected."

### WR-02: Unhandled ValueError in single-video CLI mode causes ungraceful crash

**Files modified:** `scripts/fetch-yt-analytics.py`
**Commit:** `a7fada0`
**Applied fix:** Wrapped the `persist_entry()` call in `scripts/fetch-yt-analytics.py` (single-video CLI mode) in a `try/except ValueError` block. On schema validation failure, the script now prints a user-friendly error message to stderr and exits with code 1 (matching the pattern used for other error conditions in the same function) instead of producing a raw Python traceback.

## Skipped Issues

None — all findings were fixed.

---

_Fixed: 2026-07-15T14:00:00Z_
_Fixer: the agent (gsd-code-fixer)_
_Iteration: 1_
