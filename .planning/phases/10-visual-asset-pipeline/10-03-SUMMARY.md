---
phase: 10-visual-asset-pipeline
plan: 03
subsystem: assets
tags: ["providers", "pexels", "pixabay", "freesound", "fallback-chain", "tests"]
requires:
  - 10-01 (BaseAssetProvider ABC)
  - 10-02 (storage utilities)
provides:
  - PexelsProvider — B-roll search/download via pexels.com API
  - PixabayProvider — fallback B-roll search/download via pixabay.com API
  - FreesoundProvider — SFX search/download via freesound.org API (preview URLs)
  - AssetFallbackChain — orchestrator for ordered provider fallback
affects: []
tech-stack:
  added: ["requests"]
  patterns: ["QuotaBudget.can_consume() guard", "never-raise error handling", "streaming chunked download"]
key-files:
  created:
    - agent_core/assets/providers/pexels.py
    - agent_core/assets/providers/pixabay.py
    - agent_core/assets/providers/freesound.py
    - agent_core/assets/providers/__init__.py
    - tests/test_assets/test_providers.py
  modified: []
decisions:
  - "Freesound uses preview-hq-mp3 CDN URLs instead of /download/ endpoint (avoids OAuth2 requirement)"
  - "Pixabay gets score=0.9 vs Pexels score=1.0 to signal fallback priority in ranking"
  - "All providers share same QuotaBudget instance per-process (new instance per provider init)"
  - "AssetFallbackChain mirrors TTS FallbackChain pattern exactly"
metrics:
  duration: 12m
  completed_date: 2026-07-17
  total_tasks: 3
  files_created: 5
  lines_added: 1270
  test_count: 26
  test_pass_rate: 100%
---

# Phase 10 Plan 03: Stock API Providers Summary

**One-liner:** Implemented three stock API providers (Pexels primary, Pixabay fallback, Freesound SFX) with QuotaBudget protection, never-raise error handling, and the AssetFallbackChain orchestrator — mirroring the existing TTS fallback chain pattern.

## Files Created

| File | Lines | Purpose |
|------|-------|---------|
| `agent_core/assets/providers/pexels.py` | 145 | PexelsProvider — B-roll/video search via `api.pexels.com/v1/videos/search` with Authorization header |
| `agent_core/assets/providers/pixabay.py` | 141 | PixabayProvider — fallback video search via `pixabay.com/api/videos/` with key query param |
| `agent_core/assets/providers/freesound.py` | 162 | FreesoundProvider — SFX search via `freesound.org/apiv2/search/` using preview URLs (no OAuth2) |
| `agent_core/assets/providers/__init__.py` | 136 | PROVIDERS registry, DEFAULT_FALLBACK_CHAIN, AssetFallbackChain class |
| `tests/test_assets/test_providers.py` | 686 | 26 tests covering all providers, error paths, and fallback chain |

## Task Completion

### Task 1: PexelsProvider + PixabayProvider ✅

**Commit:** `e646aac`

Both provider files created with:
- `PEXELS_API_URL` / `PIXABAY_API_URL` constants
- `__init__` loads API key from env var, logs warning if missing
- `search()` guards: missing key → `[]`, quota exhausted → `[]`
- `requests.get()` with 15s timeout, `consume()` after request
- 429 handling → returns `[]`
- `raise_for_status()`, parse JSON, build `AssetResult` list
- `download()` streams 8192-byte chunks, creates parent dirs
- All errors caught via `requests.RequestException`, returns `[]` / `None`
- Pixabay selects medium→small→tiny quality fallback

### Task 2: FreesoundProvider ✅

**Commit:** `a87590a`

- Uses `previews.preview-hq-mp3` NOT `/download/` endpoint (avoids OAuth2 — Pitfall 5)
- Falls back to `preview-lq-mp3` when HQ not available
- Duration filter: `duration:[0.1 TO 15]` for SFX-appropriate sounds
- Auth via `token` query param (not header)
- Uses `fields` parameter to limit response size
- Preview CDN URLs don't need auth headers for download

### Task 3: Provider Registry, Fallback Chain, Tests ✅

**Commit:** `7776c4a`

- `PROVIDERS = {"pexels": PexelsProvider, "pixabay": PixabayProvider, "freesound": FreesoundProvider}`
- `DEFAULT_FALLBACK_CHAIN = ["pexels", "pixabay"]`
- `AssetFallbackChain.search()` tries providers in order, returns first non-empty results
- `AssetFallbackChain.download()` routes to correct provider via `metadata["source"]`
- 26 tests: 7 Pexels, 6 Pixabay, 7 Freesound, 6 FallbackChain — all passing

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None identified. All providers are fully wired with QuotaBudget, error handling, and download logic.

## Threat Flags

None identified. All providers use external APIs with no new network surface exposed beyond what the plan specified.

## Self-Check: PASSED

- [x] `agent_core/assets/providers/pexels.py` exists (145 lines, min 120 ✓)
- [x] `agent_core/assets/providers/pixabay.py` exists (141 lines, min 110 ✓)
- [x] `agent_core/assets/providers/freesound.py` exists (162 lines, min 110 ✓)
- [x] `agent_core/assets/providers/__init__.py` exists (136 lines, min 80 ✓)
- [x] `tests/test_assets/test_providers.py` exists (686 lines, min 200 ✓)
- [x] All 3 providers importable and implement search() + download()
- [x] Missing API key → search() returns `[]`
- [x] QuotaBudget checks before API calls
- [x] 429 handling returns `[]`
- [x] All errors caught, never raise
- [x] All 26 tests pass (100%)
- [x] All 78 existing test_assets tests still pass (no regressions)
- [x] Commits: `e646aac` (T1), `a87590a` (T2), `7776c4a` (T3)
