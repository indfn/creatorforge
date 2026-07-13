---
phase: 04-ci-pipeline
plan: 03
subsystem: testing
tags: [youtube-analytics, mock-tests, unittest.mock, pytest]
requires:
  - phase: 03-test-framework
    provides: pytest infrastructure, conftest with hyphen-filename module registration
provides:
  - Mock-based test suite for YouTube Analytics fetcher (25 tests)
  - Duration parsing tests (ISO 8601)
  - Data API parsing tests (thumbnail fallback, shorts detection, error handling)
  - Analytics API parsing tests (OAuth gating, 403/5xx recovery)
  - OAuth token loading tests (missing/malformed files)
  - Main() integration test (video-not-found exits)
affects: [future analytics feature phases]
tech-stack:
  added: []
  patterns:
    - unittest.mock.patch for HTTP isolation in script tests
    - parametrized test for duration parsing edge cases
    - Hypthen-filename module import via conftest hook
key-files:
  created:
    - tests/test_scripts/__init__.py
    - tests/test_scripts/test_fetch_yt_analytics.py
  modified:
    - scripts/fetch-yt-analytics.py
requirements-completed: [TEST-09]
duration: ~15min active
completed: 2026-07-13
---

# Phase 04 Plan 03: YouTube Analytics Mock Tests Summary

**Mock-based test suite for `scripts/fetch-yt-analytics.py` — 25 tests covering Data API parsing, Analytics API parsing, duration parsing, thumbnail chain, OAuth handling, quotas/errors, and main() flow control**

## Performance

- **Duration:** ~15 min active execution
- **First commit:** 2026-07-13T03:56:04Z
- **Completed:** 2026-07-13T05:17:00Z
- **Tasks:** 1 (with automated follow-up fixes)
- **Files modified:** 3

## Accomplishments

- Created `tests/test_scripts/__init__.py` package marker
- Created 25 mock-based tests for the YouTube Analytics fetcher
- Duration parser tested with all ISO 8601 variants (seconds-only, M+S, H+M+S, empty, invalid)
- Data API tests: successful fetch, shorts/longform detection, empty items, thumbnail fallback chain (maxres→high→medium→default), missing thumbnail, HTTP 403 propagation
- Analytics API tests: successful parsing, no-OAuth returns empty, empty rows, 403 quota handling, 5xx recovery
- OAuth token tests: missing file, valid file, malformed file
- Main integration test: video-not-found exits with code 1
- load_env test: missing .env doesn't crash
- Fixed `get_oauth_token()` to catch `json.loads()` failures (previously outside try/except)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create test suite + fixtures** — `af8cdf8` (test(04-03): TEST-09)
2. **Rule 1 fix: json.loads outside try/except** — `02cf01d` (fix(04-03))

**Plan metadata:** (pending final commit)

## Files Created/Modified

- `tests/test_scripts/__init__.py` — Empty package marker
- `tests/test_scripts/test_fetch_yt_analytics.py` — Mock-based test suite (349 lines)
- `scripts/fetch-yt-analytics.py` — Fixed `get_oauth_token()` for malformed token files

## Decisions Made

- Used module-referencing `monkeypatch.setattr(mod, attr, val)` instead of dotted-path strings because monkeypatch resolves paths via `getattr()` on parent packages, but the conftest's hyphen-filename module registration doesn't set attributes on the `scripts` package

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] monkeypatch.setattr fails with dotted path for hyphen-filename modules**
- **Found during:** Task 1 (fixture setup)
- **Issue:** `monkeypatch.setattr("scripts.fetch_yt_analytics.TOKEN_PATH", ...)` fails because monkeypatch uses `getattr` on the `scripts` package to resolve the dotted path, but the conftest that registers hyphen-filename modules (like `fetch-yt-analytics.py`) puts them in `sys.modules` without setting them as attributes on the parent `scripts` package
- **Fix:** Changed all `monkeypatch.setattr` calls to import the module first, then use module-referencing calls: `monkeypatch.setattr(yt_mod, "TOKEN_PATH", ...)`
- **Files modified:** `tests/test_scripts/test_fetch_yt_analytics.py`
- **Verification:** All 25 tests pass
- **Committed in:** af8cdf8 (part of task commit)

**2. [Rule 1 - Bug] json.loads outside try/except in get_oauth_token**
- **Found during:** Task 1 (malformed token file test)
- **Issue:** `json.loads(TOKEN_PATH.read_text())` was called before the `try:` block, so a `JSONDecodeError` for malformed token files would crash instead of being caught by the existing exception handler
- **Fix:** Moved the `json.loads()` call inside the `try:` block, and added a guard for undefined `token_data` in the except handler
- **Files modified:** `scripts/fetch-yt-analytics.py`
- **Verification:** `test_malformed_token_file_returns_none` passes correctly
- **Committed in:** 02cf01d (follow-up fix commit)

**3. [Rule 3 - Deviated from Plan] TOKEN_PATH must be Path, not str**
- **Found during:** Task 1 (OAuth token tests)
- **Issue:** The plan specified `TOKEN_PATH = "/tmp/no-such-token.json"` (string), but the script calls `.exists()` on it (a `Path` method), causing `AttributeError: 'str' object has no attribute 'exists'`
- **Fix:** Used `Path("/tmp/no-such-token.json")` and `token_path` (already a Path from `tmp_path`) instead of string values
- **Files modified:** `tests/test_scripts/test_fetch_yt_analytics.py`
- **Verification:** OAuth token tests pass
- **Committed in:** af8cdf8 (part of task commit)

---

**Total deviations:** 3 auto-fixed (1 bug, 2 blocking)
**Impact on plan:** All auto-fixes necessary for correctness. No scope creep.

## Issues Encountered

- `from scripts.fetch_yt_analytics import ...` failed initially because the script filename uses hyphens (`fetch-yt-analytics.py`), not underscores. Solved by the existing conftest at `tests/test_scripts/conftest.py` which registers hyphen-filename modules via importlib.
- `monkeypatch.setattr` with dotted path strings uses `getattr()` on parent modules, incompatible with the conftest's `sys.modules`-only registration. Solved by using module-referencing monkeypatch calls.

## User Setup Required

None — all tests are fully mocked.

## Next Phase Readiness

- TEST-09 requirement is now complete (covered by 25 passing automated tests)
- YouTube Analytics fetcher has robust error handling for malformed token files
- Ready for 04-04 (Instagram Insights mock tests) and 04-05 (mock test finalization)

---

*Phase: 04-ci-pipeline*
*Completed: 2026-07-13*
