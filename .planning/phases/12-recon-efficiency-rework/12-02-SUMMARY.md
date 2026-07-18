---
phase: 12-recon-efficiency-rework
plan: 02
subsystem: recon
tags: [youtube, instagram, captions, transcript, vtt, yt-dlp, sqllite, cache, groq]
requires:
  - phase: 12-01
    provides: clean_transcript(), is_valid_transcript(), DbTranscriptCache, migrate_from_flat_cache, config updates
provides:
  - get_video_captions() — YouTube VTT caption extraction via yt-dlp
  - _process_youtube() — YouTube caption-first pipeline (cache → captions → download+transcribe)
  - _process_instagram() — Instagram caption-as-transcript (cache → caption → download+transcribe)
  - DbTranscriptCache integration with flat cache migration
  - JobConfig.target_language and Groq defaults
  - Comprehensive test coverage for caption-first paths
affects:
  - 12-03 (test suite for recon efficiency)
  - 12-04 (verification)
tech-stack:
  added: [yt-dlp subtitle extraction, SQLite transcript cache, VTT parsing]
  patterns:
    - "Per-platform caption-first methods (_process_youtube, _process_instagram)"
    - "Lazy imports for circular dependency avoidance"
    - "TDD RED/GREEN for new functions"
key-files:
  created: []
  modified:
    - agent_core/recon/scraper/youtube.py
    - agent_core/recon/skeleton_ripper/pipeline.py
    - tests/test_recon/skeleton_ripper/test_pipeline.py
key-decisions:
  - "Lazy imports for DbTranscriptCache and get_video_captions to avoid circular imports (pipeline ↔ youtube ↔ cleaning)"
  - "Multi-language caption flow: try target_language first, fall back to English, then download+transcribe"
  - "Instagram caption-as-transcript uses is_valid_transcript(min_words=10) — identical to plan D-06"
  - "YouTube _process_youtube fetches 3x videos_per_creator to buffer against caption-less videos"
patterns-established:
  - "New helpers: _make_transcript_entry(), _download_and_transcribe(), _migrate_if_empty()"
  - "transcript_source field on entries: youtube_caption, instagram_caption, whisper_api"
  - "DbTranscriptCache is lazy-imported in __init__ to avoid circular dependency"
requirements-completed:
  - RECON-EFF-01
  - RECON-EFF-03
  - RECON-EFF-06
duration: 8min
completed: 2026-07-18
---

# Phase 12 Plan 02: Caption-first pipeline — YouTube VTT extraction, Instagram caption-as-transcript, DbTranscriptCache

**YouTube caption extraction via yt-dlp + VTT parsing, per-platform pipeline methods with caption-first fallback chain, SQLite cache migration, and 44 passing tests**

## Performance

- **Duration:** 8 min
- **Started:** 2026-07-18T16:22:10+08:00
- **Completed:** 2026-07-18T16:29:38+08:00
- **Tasks:** 3 (TDD broken into RED + GREEN)
- **Files modified:** 3

## Accomplishments

- `get_video_captions(video_id, lang)` added to youtube.py — extracts YouTube auto-captions via yt-dlp subprocess, parses VTT, cleans through `clean_transcript(source="youtube_caption")`, deletes temp files
- `_process_youtube()` added to pipeline — cache → captions (target language + English fallback) → download+transcribe
- `_process_instagram()` added to pipeline — cache → caption-as-transcript (is_valid_transcript, min_words=10) → download+transcribe
- `_scrape_and_transcribe()` simplified to delegate to per-platform methods
- `DbTranscriptCache` replaces flat-file `TranscriptCache` with automatic migration on first init
- `JobConfig.target_language` added with default `"en"`; `transcribe_provider` defaults to `"groq"`
- 12 new test cases covering caption-first, caption-as-transcript, cache migration, multi-language, and fallback paths
- All 44 tests pass (32 existing + 12 new)

## Task Commits

Each task was committed atomically:

1. **Task 1 (TDD RED): Add failing test for get_video_captions** — `736d04c` (test)
2. **Task 1 (TDD GREEN): Implement get_video_captions with VTT parsing** — `e0c9f80` (feat)
3. **Task 2: Refactor pipeline with caption-first methods + DbTranscriptCache** — `0595a92` (feat)
4. **Task 3: Update pipeline test mocks for DbTranscriptCache and caption paths** — `c466b11` (test)

## Files Modified

- `agent_core/recon/scraper/youtube.py` — Added `get_video_captions()` with yt-dlp VTT extraction, lazy import for clean_transcript to avoid circular import
- `agent_core/recon/skeleton_ripper/pipeline.py` — DbTranscriptCache, per-platform methods, JobConfig.target_language, Groq defaults, flat cache migration, lazy imports for circular dependency safety
- `tests/test_recon/skeleton_ripper/test_pipeline.py` — Updated mocks (DbTranscriptCache, YouTube mocks), config assertions, 3 new test classes (12 test methods)

## Decisions Made

- **Lazy imports for circular dependency safety**: Both `DbTranscriptCache` (in `__init__`) and `get_video_captions` (in `_process_youtube`) use lazy imports because the import chain `youtube.py → skeleton_ripper/__init__ → pipeline.py → youtube.py` forms a cycle
- **YouTube buffer multiplier**: `_process_youtube` fetches 3x `videos_per_creator` to provide buffer against videos without captions
- **Instagram caption validation**: `is_valid_transcript(caption, min_words=10)` matches the plan's D-06 requirement; captions below threshold fall through to download+transcribe
- **DbTranscriptCache mocked at source module**: Since DbTranscriptCache is lazy-imported inside `__init__`, tests mock `agent_core.recon.cache.db_cache.DbTranscriptCache` (the source module) so the lazy import picks up the mock

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Circular import between youtube.py and pipeline.py**
- **Found during:** Task 1 (GREEN phase after implementation)
- **Issue:** `youtube.py` imports `clean_transcript` from `skeleton_ripper.cleaning`, which triggers `skeleton_ripper/__init__.py` which imports `pipeline.py`, which imports `get_video_captions` from `youtube.py` — circular import
- **Fix:** Made all cross-module imports lazy (inside function bodies):
  - `youtube.py`: `clean_transcript` imported inside `get_video_captions()`
  - `pipeline.py`: `get_video_captions` imported inside `_process_youtube()`
  - `pipeline.py`: `DbTranscriptCache` already lazy-imported in `__init__()`
  - Test mocks updated to patch source modules for lazy imports
- **Files modified:** `agent_core/recon/scraper/youtube.py`, `agent_core/recon/skeleton_ripper/pipeline.py`, `tests/test_recon/skeleton_ripper/test_pipeline.py`
- **Verification:** `from agent_core.recon.scraper.youtube import get_video_captions` succeeds; all 44 tests pass

**2. [Rule 1 - Bug Fix] `--timeout` flag not available in pytest runner**
- **Found during:** Final verification (pytest --timeout not installed)
- **Issue:** Plan verification step specified `--timeout=30` but pytest-timeout plugin is not installed
- **Fix:** Omitted `--timeout` flag from pytest invocation
- **Files modified:** None (test execution only)
- **Verification:** All 44 tests complete successfully without timeout flag

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** Circular import fix was essential for code to run; pytest timeout flag omission is cosmetic. No scope creep.

## Issues Encountered

- **Circular import chain:** `youtube.py → cleaning → skeleton_ripper/__init__ → pipeline → youtube.py`. Resolved by making cross-module imports lazy inside function bodies (standard Python pattern).
- **DbTranscriptCache not a module attribute:** pipeline.py lazy-imports DbTranscriptCache inside `__init__()`, so it's not available as `pipeline.DbTranscriptCache` for monkeypatching. Tests had to patch the source module instead.
- **Test db_cache migration isolation:** Cache migration tests that verify real DbTranscriptCache behavior needed to avoid the monkeypatched fixture. Resolved by using `importlib.reload()` inside test bodies to get unmocked module.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- YouTube caption extraction ready for integration with competitor analysis
- Instagram caption-as-transcript reduces download volume significantly
- Pipeline refactored to support additional platforms via new `_process_*` methods
- Flat cache migration is best-effort and already handled
- Ready for Phase 12-03 (test suite) and 12-04 (verification)

## Self-Check: PASSED

- `get_video_captions` import OK
- Pipeline imports OK
- All 4 plan commits verified (736d04c, e0c9f80, 0595a92, c466b11)
- All 44 pytest tests pass

---
*Phase: 12-recon-efficiency-rework*
*Completed: 2026-07-18*
