---
phase: 12-recon-efficiency-rework
plan: 01
subsystem: agent_core/recon
tags:
  - foundation
  - transcript-cleaning
  - sqlite-cache
  - config-defaults
  - groq
requires: []
provides:
  - clean_transcript() / is_valid_transcript()
  - DbTranscriptCache
  - Groq-as-default config
affects:
  - agent_core/recon/skeleton_ripper/pipeline.py (Plans 12-02, 12-03)
  - agent_core/recon/scraper/youtube.py (Plan 12-02)
  - agent_core/recon/scraper/instagram.py (Plan 12-03)
tech-stack:
  added:
    - sqlite3 (stdlib, threaded, WAL mode)
    - re, warnings (stdlib)
  updated:
    - python-dotenv default values for transcribe_*
key-files:
  created:
    - agent_core/recon/skeleton_ripper/cleaning.py
    - agent_core/recon/cache/__init__.py
    - agent_core/recon/cache/db_cache.py
    - tests/test_recon/test_cleaning.py
    - tests/test_recon/test_db_cache.py
  modified:
    - agent_core/recon/skeleton_ripper/cache.py (enhanced is_valid_transcript + deprecation warning)
    - agent_core/recon/config.py (Groq defaults, target_language, GROQ_API_KEY)
    - .env.example (Groq defaults + RECON_TARGET_LANGUAGE)
    - .gitignore (cache dir ignores *.txt instead of full dir)
decisions:
  - DbTranscriptCache uses min_words=2 for validation (accepts short transcripts, rejects single-word garbage)
  - GROQ_API_KEY mapped as transcribe_api_key fallback via env_map (TRANSCRIBE_API_KEY takes priority)
  - MIN_TRANSCRIPT_WORDS stays at 10; pipeline-level validation uses the higher threshold
metrics:
  duration: ~15 minutes
  completed: 2026-07-18
---

# Phase 12 Plan 01: Recon Efficiency Rework — Foundation Utilities Summary

**One-liner:** Transcript cleaning, SQLite-backed cache, and Groq-as-default config foundation laid across 5 source files with 38 passing tests.

## Completed Tasks

| # | Task | Type | Status |
|---|------|------|--------|
| 1 | Create clean_transcript() utility + enhance is_valid_transcript() | auto (tdd) | ✓ |
| 2 | Create DbTranscriptCache with SQLite + migration helper | auto (tdd) | ✓ |
| 3 | Update config.py defaults to Groq + target_language | auto | ✓ |

## Commits

| Hash | Message |
|------|---------|
| `444d5f1` | test(12-recon-efficiency-rework): add failing tests for clean_transcript and enhanced is_valid_transcript |
| `b82644f` | feat(12-recon-efficiency-rework): implement clean_transcript and enhanced is_valid_transcript |
| `f29819d` | test(12-recon-efficiency-rework): add failing tests for DbTranscriptCache and migrate_from_flat_cache |
| `66d77e7` | feat(12-recon-efficiency-rework): implement DbTranscriptCache with SQLite and migration helper |
| `37f9a54` | feat(12-recon-efficiency-rework): update config defaults to Groq and add target_language |

## Verification Results

| Check | Result |
|-------|--------|
| `cleaning import` | ✓ `from agent_core.recon.skeleton_ripper.cleaning import clean_transcript, is_valid_transcript` |
| `cache roundtrip` | ✓ `DbTranscriptCache(':memory:')` set/get/exists/clear_all |
| `config defaults` | ✓ `ReconConfig(competitors=[]).transcribe_provider == 'groq'` |
| `deprecation warning` | ✓ `TranscriptCache()` emits `DeprecationWarning` |
| `.env.example` | ✓ Shows Groq as default, GROQ_API_KEY, RECON_TARGET_LANGUAGE |
| All tests | ✓ 38/38 passing |

## What Was Built

### Task 1: Transcript Cleaning (`cleaning.py` + enhanced `cache.py`)

- **`clean_transcript(raw, source)`** handles three source types:
  - `youtube_caption`: Strips `[Music]`, `[Applause]`, `[♪]`, WEBVTT headers, cue timing lines, cue numbering, HTML entities, repeated consecutive words, multi-whitespace, zero-width characters
  - `whisper`: Normalizes whitespace, strips incomplete trailing sentences, strips zero-width characters
  - `instagram_caption`: Normalizes Unicode quotes to ASCII, collapses excess blank lines, strips zero-width characters
- **Enhanced `is_valid_transcript()`**: Added `min_words` parameter (default `MIN_TRANSCRIPT_WORDS=10`) and `min_word_length` parameter (default 1, filters single-char garbage)
- Exported from both `cache.py` and `cleaning.py`

### Task 2: SQLite-Backed Cache (`cache/db_cache.py`)

- **`DbTranscriptCache`** class with SQLite (WAL mode, `busy_timeout=5000`, `row_factory=sqlite3.Row`):
  - Schema: `(id, platform, username, video_id, transcript_text, word_count, source, language, created_at, last_accessed_at, ttl_seconds)`
  - Methods: `get()`, `set()`, `exists()`, `clear_all()`, `get_stats()`
  - TTL eviction: entries deleted on read when expired
  - Thread-safe via `threading.Lock`
  - Default TTL: 30 days
  - `set()` validates with `min_words=2` (rejects single-word garbage)
- **`migrate_from_flat_cache()`**: Scans `{platform}_{username}_{video_id}.txt` files, parses filename, calls `db_cache.set()` with `source="migrated"`
- **DeprecationWarning** added to `TranscriptCache.__init__()` pointing to `DbTranscriptCache`

### Task 3: Config + .env.example Updates

| Field | Old Default | New Default |
|-------|-------------|-------------|
| `transcribe_provider` | `"openai"` | `"groq"` |
| `transcribe_base_url` | `"https://api.openai.com/v1"` | `"https://api.groq.com/openai/v1"` |
| `transcribe_model` | `"whisper-1"` | `"whisper-large-v3-turbo"` |
| `target_language` | (none) | `"en"` |

- `GROQ_API_KEY` → `transcribe_api_key` fallback (via env_map), `TRANSCRIBE_API_KEY` takes priority
- `RECON_TARGET_LANGUAGE` → `target_language` via env_map
- `.env.example` section updated with Groq defaults, `GROQ_API_KEY`, `RECON_TARGET_LANGUAGE`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] VTT cue numbers not stripped**
- **Found during:** Task 1 RED phase
- **Issue:** Test `test_youtube_caption_strips_webvtt_header` revealed that VTT cue numbering lines (e.g., `1`, `2`) before timing lines were not being stripped
- **Fix:** Added `VTT_CUE_NUMBER` regex and filtering alongside timing line check
- **Files:** `cleaning.py`

**2. [Rule 1 - Bug] `_strip_incomplete_sentence` returned empty for text without sentence punctuation**
- **Found during:** Task 1 RED phase
- **Issue:** Whisper text without any sentence-ending punctuation (e.g., `"hello world"`) was reduced to empty string
- **Fix:** Added guard to return original text when only one "sentence" segment exists without punctuation
- **Files:** `cleaning.py`

**3. [Rule 1 - Bug] Instagram blank line collapsing off by one**
- **Found during:** Task 1 RED phase
- **Issue:** `4` consecutive blank lines collapsed to `3` instead of `1`
- **Fix:** Changed threshold logic to only append one blank line per consecutive group (`blank_count == 1`)
- **Files:** `cleaning.py`

**4. [Rule 1 - Bug] Missing `row_factory` on sqlite3 connection**
- **Found during:** Task 2 RED phase
- **Issue:** `row["column_name"]` failed with tuple index error — sqlite3 default row factory returns tuples
- **Fix:** Added `self._conn.row_factory = sqlite3.Row` after connection
- **Files:** `db_cache.py`

**5. [Rule 2 - Missing] Env map ordering for GROQ_API_KEY vs TRANSCRIBE_API_KEY priority**
- **Found during:** Task 2 implementation review
- **Issue:** Initial env_map had GROQ_API_KEY after TRANSCRIBE_API_KEY, meaning GROQ would overwrite TRANSCRIBE when both set
- **Fix:** Reordered so GROQ_API_KEY comes first (fallback, overwritten by TRANSCRIBE_API_KEY)
- **Files:** `config.py`

### Design Adjustments

- **Plan vs Behavior conflict:** Plan says `MIN_TRANSCRIPT_WORDS=10` but behavior examples show `is_valid_transcript("hello world")` returning True (2 words). Resolved by keeping `MIN_TRANSCRIPT_WORDS=10` for pipeline-level validation and using `min_words=2` for cache-level validation. Tests aligned with the explicit plan directives.

## Threat Surface Scan

No new threat surface beyond what was analyzed in the plan's `<threat_model>`:
- T-12-01 (SQLite file): Accepted — local file, same user, WAL mode prevents corruption
- T-12-02 (.env.example placeholder): Mitigated — no real key committed
- T-12-03 (clean_transcript input): Mitigated — returns empty string on exception, no eval/exec

## Self-Check: PASSED

- [x] `agent_core/recon/skeleton_ripper/cleaning.py` exists (120+ lines)
- [x] `agent_core/recon/cache/db_cache.py` exists (280+ lines)
- [x] `agent_core/recon/cache/__init__.py` exists
- [x] `tests/test_recon/test_cleaning.py` exists (17 tests pass)
- [x] `tests/test_recon/test_db_cache.py` exists (21 tests pass)
- [x] All 38 tests pass
- [x] Config defaults verified correct
- [x] `.env.example` updated with Groq defaults
- [x] DeprecationWarning verified on `TranscriptCache()`
- [x] No unexpected deletions in commits
