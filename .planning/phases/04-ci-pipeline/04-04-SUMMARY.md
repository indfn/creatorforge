---
phase: 04-ci-pipeline
plan: 04
subsystem: tests
tags: [test, instagram, mock, insights]
requires: [04-01]
provides: [TEST-10]
affects: [scripts/fetch-ig-insights.py]
tech-stack:
  added: []
  patterns: ["unittest.mock.patch", "importlib-based module registration", "parametrized mock responses"]
key-files:
  created:
    - tests/test_scripts/test_fetch_ig_insights.py
    - scripts/__init__.py
  modified: []
decisions: []
metrics:
  duration: ~5m
  tasks: 1
  total_tests: 19
  passed: 19
  coverage_areas: 7
---

# Phase 04 Plan 04: Instagram Insights Mock Tests — Summary

Comprehensive mock-based test suite for `scripts/fetch-ig-insights.py` covering media insights parsing, engagement rate calculation, follower delta computation, error handling, caption truncation, and main() orchestration.

## Results

- **19 tests total** across 7 test classes — all pass
- **Zero real network requests** — all HTTP calls mocked via `unittest.mock.patch('requests.get')`
- **Both media types covered:** VIDEO (with plays/views) and IMAGE (no plays)

## Files Created

| File | Purpose |
|------|---------|
| `tests/test_scripts/test_fetch_ig_insights.py` | 19 mock-based tests for Instagram Insights fetcher |
| `scripts/__init__.py` | Package init with lazy-loading for hyphen-named script modules (fixes importability of `fetch-ig-insights.py`, `fetch-yt-analytics.py`, etc.) |

## Test Coverage

| Test Class | Tests | What It Covers |
|------------|-------|----------------|
| `TestGetMediaInsights` | 7 | VIDEO basic fields, VIDEO insights metrics, engagement rate calc, IMAGE no-plays, IMAGE engagement via reach, 400 error handling, 500 error handling |
| `TestGetFollowerDelta` | 5 | Positive delta, single-value returns None, negative clamped to 0, missing data, API error |
| `TestGetRecentMedia` | 2 | Returns media list, empty list |
| `TestMain` | 3 | Missing access token (sys.exit), missing account ID (sys.exit), --media-id end-to-end flow |
| `TestCaptionTruncation` | 1 | 200-char caption truncated to 100 |
| `TestEnvLoading` | 1 | `load_env` doesn't crash when `.env` missing |

## Engagement Rate Verification

- **VIDEO:** (200 + 50 + 100 + 300) / 10000 × 100 = **6.5%** ✓
- **IMAGE:** (100 + 20 + 75 + 150) / 5000 × 100 = **6.9%** ✓

## Commits

- `a5e9b24` — test(04-04): TEST-10: mock-based Instagram Insights fetcher tests

## Verifications

- `pytest tests/test_scripts/test_fetch_ig_insights.py -v --tb=short` — exit 0, 19 passed ✓
- All HTTP calls mocked — no real network requests ✓
- Both media types tested: VIDEO (with plays) and IMAGE (no plays) ✓
- Engagement rate verified with hand-calculated expected values ✓
- Follower delta tested: positive, negative clamped to 0, single-value returns None ✓
- Error handling: 400 silently handled, 500 returns empty, missing env var sys.exits ✓

## Deviations from Plan

### [Rule 3 - Blocking] Fixed importability of hyphen-named scripts

- **Found during:** Task 1 — module import
- **Issue:** The file `scripts/fetch-ig-insights.py` uses hyphens in its filename, making it impossible to import as `scripts.fetch_ig_insights` (Python identifiers can't contain hyphens). All 19 test functions used `from scripts.fetch_ig_insights import ...` which would fail with `ModuleNotFoundError`.
- **Fix:** Created `scripts/__init__.py` with a lazy-loading mechanism using `__getattr__` that registers hyphen-named script modules in `sys.modules` under their underscored names. This also fixes the same issue for `fetch-yt-analytics.py`, `generate-pdf.py`, and other scripts in the directory. The existing `test_fetch_yt_analytics.py` tests also benefited from this fix (they were broken before).
- **Files modified:** `scripts/__init__.py` (new file — 72 lines)
- **Commit:** `a5e9b24`

## Known Stubs

None — all test data is inline and complete.

## Threat Flags

None — test files introduce no new attack surface. `scripts/__init__.py` safely loads only known local files and cannot be exploited for arbitrary code execution.

## Self-Check: PASSED

- [x] `tests/test_scripts/test_fetch_ig_insights.py` exists
- [x] `scripts/__init__.py` exists
- [x] Commit `a5e9b24` exists in git log
- [x] All 19 tests pass with `pytest tests/test_scripts/test_fetch_ig_insights.py -v`
