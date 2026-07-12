---
phase: 02-security-hardening
plan: 03
subsystem: api, security
tags: [flask, argparse, api-security, input-validation, packaging]

# Dependency graph
requires:
  - phase: 02-01
    provides: pyproject.toml packaging, pip install -e . package resolution
provides:
  - Flask app entry point hardening (--debug/--host CLI flags, 127.0.0.1 default)
  - Settings API whitelist with URL/provider value validation
  - Removed all sys.path.insert hacks across codebase
affects: [03-testing, deployment, production-run]

# Tech tracking
tech-stack:
  added: [argparse]
  patterns: [CLI flags for server config, frozenset whitelist for API input validation]

key-files:
  modified:
    - agent_core/recon/web/app.py
    - agent_core/recon/bridge.py
    - agent_core/scoring/rescore.py

key-decisions:
  - "Used frozenset for SETTINGS_WHITELIST (immutable, hashable, communicates intent)"
  - "Rejected keys reported as warning in response, not error (partial updates succeed)"
  - "Kept import sys in rescore.py for sys.argv/sys.exit usage"
  - "Empty/null values silently skipped (preserves existing partial-update behavior)"

patterns-established:
  - "API input validation: whitelist + format check + enum check before persistence"
  - "Flask binding: default to localhost only, require explicit --host for LAN access"

requirements-completed: [SEC-02, SEC-04, SEC-06, SEC-08]
duration: 12min
completed: 2026-07-12
---

# Phase 2 Plan 3: Flask Hardening & sys.path Cleanup Summary

**Flask app hardened with argparse --debug/--host flags (127.0.0.1 default), settings API whitelist with URL/provider validation, and all sys.path.insert hacks removed**

## Performance

- **Duration:** 12 min
- **Started:** 2026-07-12T09:41:23Z
- **Completed:** 2026-07-12T09:53:46Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- **SEC-06:** Removed all 3 `sys.path.insert(0, ...)` hacks from `app.py`, `bridge.py`, and `rescore.py` — all `agent_core.*` imports now resolve via installed package metadata
- **SEC-02 + SEC-08:** Flask entry point hardened: `debug=False` by default, binds to `127.0.0.1` by default; `--debug`, `--host`, `--port` CLI flags for explicit overrides
- **SEC-04:** Settings API (`api_save_settings`) protected with `SETTINGS_WHITELIST` frozenset (9 allowed keys); URL values validated for `http://`/`https://` prefix; `transcribe_provider` restricted to `openai`/`local`; rejected keys reported as warnings

## Task Commits

Each task was committed atomically:

1. **Task 1: SEC-06 — Remove sys.path.insert hacks** — `621ea53` (fix)
2. **Task 2: SEC-02 + SEC-08 — argparse --debug/--host flags** — `bb7ae97` (fix)
3. **Task 3: SEC-04 — SETTINGS_WHITELIST + validation** — `d942c8e` (fix)

## Files Modified

- `agent_core/recon/web/app.py` — Removed sys.path.insert, added argparse --debug/--host/--port, added SETTINGS_WHITELIST + hardened api_save_settings
- `agent_core/recon/bridge.py` — Removed import sys + sys.path.insert, rewritten imports to agent_core.* style
- `agent_core/scoring/rescore.py` — Removed sys.path.insert (kept import sys for sys.argv/exit)

## Decisions Made

- Used `frozenset` for `SETTINGS_WHITELIST` — immutable, hashable, clearly communicates that it shouldn't be modified at runtime
- Rejected keys reported as `warning` in JSON response (not error) — partial updates with valid keys still succeed
- Empty/null values silently skipped — preserves existing partial-update behavior for settings forms
- `import sys` kept in `rescore.py` because `sys.argv` and `sys.exit()` are used throughout the file
- `PROJECT_ROOT` kept in `rescore.py` — still used for data directory resolution

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

- Pre-existing uncommitted import-rewrite changes from Plan 02-01 (`recon.*` → `agent_core.recon.*` style) were in working tree and committed together with Task 1 edits. These were necessary changes that had been left unstaged.
- `instaloader` missing from environment initially blocked full import verification — installed it to complete verification.

## Threat Surface Scan

No new threat surface introduced. All changes reduce existing surface:

| Threat (from plan) | Disposition | Status |
|---|---|---|
| T-02-07 — Flask debug mode EoP | **mitigate** | debug=False default; --debug flag requires explicit opt-in |
| T-02-08 — Flask network binding info disclosure | **mitigate** | 127.0.0.1 default; --host 0.0.0.0 requires explicit opt-in |
| T-02-09 — Settings API tampering | **mitigate** | Whitelist + URL validation + provider enum restriction |
| T-02-10 — PROXY_URL/GEMINI_API_KEY spoofing | **accept** | Already accepted in plan |

## Next Phase Readiness

- Phase 2 Security Hardening complete (all 3 plans executed)
- Ready for Phase 3: Testing — all Flask routes, settings API, and credential flows can now be tested with proper security controls in place

---
*Phase: 02-security-hardening*
*Plan: 03*
*Completed: 2026-07-12*
