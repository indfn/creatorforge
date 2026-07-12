---
phase: 02-security-hardening
fixed_at: 2026-07-12T12:00:00Z
review_path: .planning/phases/02-security-hardening/02-REVIEW.md
iteration: 1
findings_in_scope: 4
fixed: 4
skipped: 0
status: all_fixed
---

# Phase 02: Code Review Fix Report

**Fixed at:** 2026-07-12T12:00:00Z
**Source review:** .planning/phases/02-security-hardening/02-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 4 (1 critical, 3 warnings)
- Fixed: 4
- Skipped: 0

## Fixed Issues

### CR-01: Wrong PROJECT_ROOT path in rescore.py breaks data directory resolution

**Files modified:** `agent_core/scoring/rescore.py`
**Commit:** b0cc118
**Applied fix:** Changed `PROJECT_ROOT = Path(__file__).parent.parent` to `PROJECT_ROOT = Path(__file__).parent.parent.parent`. The file lives at `agent_core/scoring/rescore.py`, so 3 levels up correctly resolves to the project root (matching the same convention used by `config.py` and `bridge.py`). This fixes `data/topics/` lookups in `find_latest_topics_file()` and relative path resolution in CLI mode.

### WR-01: `weights` parameter passed but never consumed in `skeleton_to_topic()`

**Files modified:** `agent_core/recon/bridge.py`
**Commit:** f58323f
**Applied fix:** Removed the unused `weights: Dict[str, float]` parameter from `skeleton_to_topic()` function signature and removed the `weights=weights` argument from the single call site in `generate_topics_from_skeletons()`. Scoring is delegated entirely to `engine_score_topic()`, which has its own weight-handling logic, so the parameter was dead.

### WR-02: Broad `except` catches `KeyboardInterrupt` and `SystemExit`

**Files modified:** `agent_core/recon/config.py`
**Commit:** 90dccde
**Applied fix:** Replaced `except (InvalidToken, Exception):` with `except Exception:`. Since `InvalidToken` is a subclass of `Exception`, listing it separately was redundant. More importantly, `KeyboardInterrupt` and `SystemExit` inherit from `BaseException` (not `Exception`), so they now propagate correctly instead of being silently swallowed. Also removed the now-unused `InvalidToken` import.

### WR-03: `app.test_request_context()` used inside live request for internal routing

**Files modified:** `agent_core/recon/web/app.py`
**Commit:** 1f74129
**Applied fix:** Extracted the shared scrape-job-starting logic from `api_scrape_competitor()` into a standalone `_scrape_competitor(handle_clean, max_reels)` helper function that does not depend on Flask's request context. Both `api_scrape_competitor()` and `api_scrape_all()` now call this helper directly:

- `api_scrape_competitor()` reads `max_reels` from the request and passes it to `_scrape_competitor()`
- `api_scrape_all()` calls `_scrape_competitor()` in a loop for each competitor, eliminating the fragile `app.test_request_context()` sub-request pattern entirely

This avoids `RuntimeError: Working outside of request context` issues with threaded WSGI servers and removes context leak risks.

---

_Fixed: 2026-07-12T12:00:00Z_
_Fixer: the agent (gsd-code-fixer)_
_Iteration: 1_
