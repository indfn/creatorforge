---
phase: 05-channel-onboarding-branding
plan: 01
status: READY_FOR_EXECUTION
wave: 1
requirements: [CHANNEL-01]
tasks: 2
files_created:
  - agent_core/publishing/oauth.py (replace stubs with full implementation)
  - scripts/setup-yt-oauth.py (refactor to thin wrapper)
---

# Phase 05 Plan 01: OAuth Core Module — Summary

**Status:** READY_FOR_EXECUTION

## Objective

Implement the OAuth core module in `agent_core/publishing/oauth.py` with full token lifecycle management, and refactor `scripts/setup-yt-oauth.py` into a thin CLI wrapper that delegates to the core module.

## Scope

| Requirement | Description |
|-------------|-------------|
| CHANNEL-01 | Complete OAuth 2.0 flow with offline access for channel management; token per channel with auto-refresh |

## Decisions Implemented

| Decision | Implementation |
|----------|---------------|
| D-01 | `get_authenticated_service()` and `refresh_token_if_expired()` in `agent_core/publishing/oauth.py` |
| D-02 | `setup-yt-oauth.py` calls `save_initial_token()` from core module |
| D-04 | Single OAuth entry point for Phases 5, 6, 7 |
| D-08 | Credentials passed to `build("youtube", "v3", credentials=creds, static_discovery=False)` — auto-refresh |
| D-10 | Token at `channels/{Name}/yt-oauth-token.json` |
| D-11 | All error messages include actionable next commands |
| D-12 | No silent failures — context printed for all errors |

## Task Breakdown

### Task 1: Implement `agent_core/publishing/oauth.py`
- 4 public functions: `save_initial_token()`, `get_or_refresh_credentials()`, `get_authenticated_service()`, `refresh_token_if_expired()`
- 3 private helpers: `_project_root()`, `_token_path()`, `_load_token_data()`
- Constant `SCOPES` — exported for use by scripts (avoids duplication)
- Standard token JSON format: `{token, refresh_token, token_uri, client_id, client_secret, scopes}`
- `static_discovery=False` on `build()` — required for environments without cached discovery docs

### Task 2: Refactor `scripts/setup-yt-oauth.py`
- Removes inline token dict construction and `json.dumps`/`write_text`
- Imports `save_initial_token` and `SCOPES` from core module
- Keeps browser OAuth flow (`InstalledAppFlow.run_local_server`)
- Keeps all validation checks (channel dir, client_secret existence)
- Removes standalone `json` import

## Threat Model

| ID | Category | Disposition | Detail |
|----|----------|-------------|--------|
| T-05-01 | Information Disclosure | Accept | Token file is plain JSON (per D-10); sits in gitignored `channels/` dir |
| T-05-02 | Spoofing | Accept | Credentials object from google-auth-oauthlib — library validates OAuth response |
| T-05-03 | Elevation of Privilege | Mitigate | Path constrained to `channels/{channel}/yt-oauth-token.json` — no traversal risk |

## Downstream Impact

- `scripts/setup-channel-branding.py` imports `get_authenticated_service()` in Plan 05-02 (CHANNEL-02) — will replace inline Credentials building
- Phase 6 (publishing) imports `get_authenticated_service()` and `get_or_refresh_credentials()`
- Phase 7 (analytics) imports `get_or_refresh_credentials()`
