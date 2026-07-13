# Phase 05-02 SUMMARY: Channel Branding API

**Status:** READY_FOR_EXECUTION
**Requirements covered:** CHANNEL-02, CHANNEL-03, CHANNEL-04, CHANNEL-05
**Depends on:** 05-01 (core OAuth module implementation)
**Wave:** 2

## Objective

Refactor `scripts/setup-channel-branding.py` to use the core OAuth module (`get_authenticated_service()`) instead of rebuilding Credentials inline. Add manual-only avatar handling (CHANNEL-03) with path persistence. Update agent documentation.

## Key Decisions

- **D-03**: `setup-channel-branding.py` uses `get_authenticated_service()` from core OAuth module
- **D-04**: Single OAuth entry point across all phases
- **D-05**: CHANNEL-03 (avatar) is manual-only — YouTube Data API v3 has no avatar endpoint
- **D-06**: `avatar_path` stored in `channel_config.json["branding"]["avatar_path"]` for documentation
- **D-07**: documented in `viral-onboard.md` and `REQUIREMENTS.md`
- **D-13**: Missing avatar/banner files skipped with clear warning, not crash

## Tasks

| # | Task | Files | Type |
|---|------|-------|------|
| 1 | Refactor OAuth credential loading + keep existing branding API logic | `scripts/setup-channel-branding.py` | auto |
| 2 | Add CHANNEL-03 avatar manual-only handling + update docs | `scripts/setup-channel-branding.py`, `.agents/commands/viral-onboard.md`, `.planning/REQUIREMENTS.md` | auto |

## Verification

1. Syntax check: `python3 -c "import ast; ast.parse(open('scripts/setup-channel-branding.py').read())"`
2. No dead code: `grep -c "load_token\|Credentials\|build(\"youtube\"" scripts/setup-channel-branding.py` → 0
3. OAuth import present: `grep -c "get_authenticated_service" scripts/setup-channel-branding.py` → 1
4. Avatar handling present: `grep -c "avatar" scripts/setup-channel-branding.py` → ≥1
5. Docs updated: `grep -c "avatar" .agents/commands/viral-onboard.md` → ≥1
6. Requirements updated: `grep -c "manual-only" .planning/REQUIREMENTS.md` → ≥1

## Success Criteria

1. `scripts/setup-channel-branding.py` uses core OAuth module — zero inline credential code
2. All branding operations work: description, keywords, country, language, banner, watermark
3. Avatar flag stores path and prints manual instructions — no API call
4. `viral-onboard.md` updated with avatar limitation
5. `REQUIREMENTS.md` CHANNEL-03 notes manual-only
