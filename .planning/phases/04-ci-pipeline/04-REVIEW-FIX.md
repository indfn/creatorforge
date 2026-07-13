---
phase: 04-ci-pipeline
fixed_at: 2026-07-13T18:45:00Z
review_path: .planning/phases/04-ci-pipeline/04-REVIEW.md
iteration: 1
findings_in_scope: 5
fixed: 5
skipped: 0
status: all_fixed
---

# Phase 04: Code Review Fix Report

**Fixed at:** 2026-07-13T18:45:00Z
**Source review:** .planning/phases/04-ci-pipeline/04-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 5
- Fixed: 5
- Skipped: 0

## Fixed Issues

### WR-01: Unused `media_type` parameter in `get_media_insights`

**Files modified:** `scripts/fetch-ig-insights.py`, `tests/test_scripts/test_fetch_ig_insights.py`
**Commit:** `b740a94`
**Applied fix:** Removed the unused `media_type` parameter from `get_media_insights()` function definition. Updated the call site in `main()` (line 248) and all test call sites (3 occurrences) that were passing `media_type="IMAGE"` as a keyword argument.

### WR-02: Dead code — `fetch_ctr` always returns `None` and is never called

**Files modified:** `scripts/fetch-yt-analytics.py`
**Commit:** `53086cd`
**Applied fix:** Removed the entire `fetch_ctr` function (~30 lines). The function overwrote its own `metrics` parameter (set `cardClickRate`, then overwrote with `views`), always returned `None`, and was never called by `main()`. The CTR fallback note in `main()` (lines 268-270 of the original) remains as the sole handler.

### WR-03: Overly broad exception handling with fragile `locals()` check in `get_oauth_token`

**Files modified:** `scripts/fetch-yt-analytics.py`
**Commit:** `33887c1`
**Applied fix:** Refactored `get_oauth_token()` to split the try/except into two blocks:
- First block: `json.loads` + `read_text()` with narrow `except (json.JSONDecodeError, OSError)` — returns `None` early on file I/O failure.
- Second block: OAuth credential operations with `except Exception` — `token_data` is guaranteed to be defined here (early return from block 1 on failure), so `token_data.get("token")` is safe without `locals()` introspection.

### WR-04: Coverage configuration excludes `scripts/` from tracking

**Files modified:** `pyproject.toml`
**Commit:** `d8a58f9`
**Applied fix:** Added `"scripts"` to `[tool.coverage.run]` `source` list, and removed `"*/scripts/*"` and `"*/production/*"` from the `omit` list. This allows `pytest --cov=scripts` to measure coverage of the analytics scripts which have dedicated test suites.

### WR-05: Missing timeout and connection error coverage in analytics tests

**Files modified:** `tests/test_scripts/test_fetch_yt_analytics.py`, `tests/test_scripts/test_fetch_ig_insights.py`
**Commit:** `2245602`
**Applied fix:** Added 8 new test cases across both test suites:
- **`test_fetch_yt_analytics.py` — `TestFetchDataApi`:** `test_timeout_propagates` and `test_connection_error_propagates` (verify Timeout/ConnectionError propagate through `fetch_data_api`)
- **`test_fetch_yt_analytics.py` — `TestFetchAnalyticsApi`:** `test_timeout_returns_empty` and `test_connection_error_returns_empty` (verify Timeout/ConnectionError are caught by generic except and return `{}`)
- **`test_fetch_ig_insights.py` — `TestGetMediaInsights`:** `test_media_fields_timeout_propagates`, `test_media_fields_connection_error_propagates`, `test_insights_timeout_propagates`, and `test_insights_connection_error_propagates` (verify Timeout/ConnectionError propagate from both the media fields and insights requests)

---

_Fixed: 2026-07-13T18:45:00Z_
_Fixer: the agent (gsd-code-fixer)_
_Iteration: 1_
