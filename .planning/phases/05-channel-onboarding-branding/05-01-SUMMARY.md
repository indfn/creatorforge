---
phase: 05-channel-onboarding-branding
plan: 01
type: execute
wave: 1
subsystem: publishing
tags: [oauth, youtube, auth, token-management]
requires: [CHANNEL-01]
provides: [oauth-core-module]
affects: [scripts/setup-yt-oauth.py, agent_core/publishing/oauth.py]
tech-stack:
  added: [google-auth, google-auth-oauthlib, google-api-python-client]
  patterns: [OAuth token lifecycle, auto-refresh, per-channel credentials]
key-files:
  created:
    - agent_core/publishing/oauth.py
  modified:
    - scripts/setup-yt-oauth.py
    - pyproject.toml
decisions:
  - D-01: OAuth token lifecycle in agent_core/publishing/oauth.py
  - D-02: setup-yt-oauth.py becomes thin CLI wrapper
  - D-04: oauth.py is single OAuth entry point for Phases 5, 6, 7
  - D-08: get_authenticated_service() loads token → builds Credentials → passes to youtube.build() with auto-refresh
  - D-10: Token persisted per-channel at channels/{Name}/yt-oauth-token.json
  - D-11: Error messages include exact next command user should run
  - D-12: No silent failures
metrics:
  duration: "~5 min"
  completed: "2026-07-13"
---

# Phase 5 Plan 01: CHANNEL-01 — OAuth Core Module Summary

**One-liner:** Implemented `agent_core/publishing/oauth.py` with 4 public functions covering the full OAuth token lifecycle (save, load, refresh, build API service), and refactored `scripts/setup-yt-oauth.py` into a thin CLI wrapper that delegates token persistence to the core module.

## Commit

| Hash | Message |
|------|---------|
| `c5ca27a` | `feat(05-01): CHANNEL-01: implement OAuth core module with auto-refresh` |

## Files

### Created
- `agent_core/publishing/oauth.py` — 250-line OAuth core module with 4 public functions:
  - `save_initial_token(channel, credentials)` — persists Credentials to per-channel JSON file
  - `get_or_refresh_credentials(channel)` — loads token, refreshes if expired, returns valid Credentials
  - `get_authenticated_service(channel)` — builds authenticated YouTube API Resource via `build("youtube", "v3", credentials=creds, static_discovery=False)`
  - `refresh_token_if_expired(channel)` — public wrapper, returns True if valid/fresh, False if refresh fails
  - Private helpers: `_project_root()`, `_token_path()`, `_load_token_data()`

### Modified
- `scripts/setup-yt-oauth.py` — Refactored to thin CLI wrapper:
  - Imports `save_initial_token` and `SCOPES` from core module
  - Removes inline `token_data` dict construction and `json.dumps` serialization
  - Removes `json` import (no longer needed)
  - Preserves OAuth browser flow (`run_local_server`), argparse, validation checks
- `pyproject.toml` — Added `N999` per-file ignore for `scripts/*` (hyphenated filenames are standard project convention)

## Verification Results

| Check | Result |
|-------|--------|
| `from agent_core.publishing.oauth import (4 public functions)` | ✅ Passed |
| `ruff check agent_core/publishing/oauth.py` | ✅ Clean |
| `ruff check scripts/setup-yt-oauth.py` | ✅ Clean |
| `mypy agent_core/publishing/oauth.py` | ✅ Clean |
| `python scripts/setup-yt-oauth.py --help` | ✅ Works |
| No `json` import in script | ✅ Confirmed |
| `SCOPES` not defined locally in script | ✅ Confirmed |
| `static_discovery=False` in `build()` call | ✅ Confirmed |
| `google.auth.transport.requests.Request()` used for refresh | ✅ Confirmed |
| `logging` used for warnings | ✅ Confirmed |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Missing ruff and mypy in virtual environment**
- **Found during:** Verification step
- **Issue:** `ruff` and `mypy` not installed in `.venv/`, causing verification commands to fail
- **Fix:** Installed `ruff` and `mypy` via `pip install`
- **Files modified:** (none — only venv state changed)

**2. [Rule 3 - Blocking] F541 f-string without placeholders**
- **Found during:** `ruff check scripts/setup-yt-oauth.py`
- **Issue:** `print(f"Scopes: channel management + video upload + analytics read")` had a redundant `f` prefix
- **Fix:** Removed extraneous `f` prefix
- **Files modified:** `scripts/setup-yt-oauth.py`

**3. [Rule 2 - Missing critical config] N999 module naming rule flagged hyphenated script filenames**
- **Found during:** `ruff check scripts/setup-yt-oauth.py`
- **Issue:** Ruff's `N999` rule flagged all scripts in `scripts/` for having hyphens in filenames (e.g., `setup-yt-oauth.py`), which is a standard project convention
- **Fix:** Added `"N999"` to the existing `scripts/*` per-file ignore in `pyproject.toml`
- **Files modified:** `pyproject.toml`

## Key Decisions Applied

- **D-01:** OAuth token lifecycle centralized in `agent_core/publishing/oauth.py`
- **D-02:** `scripts/setup-yt-oauth.py` delegates persistence to core module
- **D-08:** Credentials passed to `youtube.build()` — google-api-python-client handles auto-refresh on 401
- **D-10:** Token stored at `channels/{Name}/yt-oauth-token.json`
- **D-11:** All error messages include actionable next commands
- **D-12:** All errors surface with context (no silent failures)

## Threat Surface Check

No new threat surface introduced beyond what the plan documented in T-05-01 through T-05-03. Token file paths are constrained to `channels/{channel}/yt-oauth-token.json` (path traversal mitigated). Credentials come from google-auth-oauthlib's validated `run_local_server()` flow.

## Known Stubs

- `agent_core/publishing/metadata.py` — Exists but not committed (will be implemented in later phase)
- `agent_core/publishing/scheduler.py` — Exists but not committed (will be implemented in later phase)
- `agent_core/publishing/uploader.py` — Exists but not committed (will be implemented in later phase)

These are pre-existing stubs in the `agent_core/publishing/` directory that were never committed. They are not part of this plan's scope.

## Self-Check: PASSED

- ✅ `agent_core/publishing/oauth.py` exists with 250 lines
- ✅ All 4 public functions import successfully
- ✅ ruff lint passes on both modified files
- ✅ mypy type-check passes on core module
- ✅ `--help` works for setup script
- ✅ No `json` import in setup script
- ✅ `SCOPES` not defined locally in setup script
- ✅ Commit `c5ca27a` exists in git log
