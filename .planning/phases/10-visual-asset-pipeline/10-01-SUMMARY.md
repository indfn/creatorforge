---
phase: 10-visual-asset-pipeline
plan: 01
subsystem: assets, cache, testing
tags: [sqlite, abc, dataclass, pytest, portalocker, hashlib]
requires: []
provides:
  - AssetResult dataclass with source_url, file_extension, metadata, score
  - BaseAssetProvider ABC enforcing search() and download() contracts
  - Storage helpers: consistent_asset_path, temp_asset_dir, compute_content_hash, build_asset_filename
  - AssetCache SQLite-backed with TTL eviction (permanent and time-limited entries)
  - Search query generators: generate_search_query, generate_sfx_query
  - Test fixtures: mock API responses, temp cache, env var isolation
affects:
  - Phase 10 providers (Pexels, Pixabay, Freesound) will consume BaseAssetProvider ABC
  - Phase 10 characters module will use storage and cache
  - Phase 11 production pipeline will use asset resolution

tech-stack:
  added: []
  patterns:
    - ABC + dataclass pattern (mirrors agent_core/audio/tts/base.py)
    - SQLite with WAL mode + threading.Lock (Pitfall 3 mitigation)
    - Cache-aside pattern with file existence validation (Pitfall 2 / T-10-03)
    - Channel validation regex ^[A-Za-z0-9_-]+$ (T-10-01)
    - _project_root() via Path(__file__).resolve().parent.parent.parent
    - SHA-256 content hashing truncated to 8 hex chars (D-15)

key-files:
  created:
    - agent_core/assets/__init__.py (14 lines)
    - agent_core/assets/base.py (79 lines)
    - agent_core/assets/storage.py (184 lines)
    - agent_core/assets/cache.py (298 lines)
    - agent_core/assets/search.py (83 lines)
    - tests/test_assets/__init__.py (0 lines)
    - tests/test_assets/conftest.py (152 lines)
    - tests/test_assets/test_base.py (145 lines)
    - tests/test_assets/test_storage.py (175 lines)
    - tests/test_assets/test_cache.py (292 lines)
  modified: []

key-decisions:
  - "Timestamp comparison uses Python ISO format strings for both expires_at and query to avoid microsecond precision mismatch with SQLite datetime('now')"
  - "Cache file existence validation (Pitfall 2) takes precedence over simple cache HIT — prevents returning stale/stolen file references (T-10-03)"
  - "threading.Lock instead of file-level portalocker for SQLite — sufficient for single-process with WAL mode + busy_timeout"

patterns-established:
  - "Asset resolution path: global assets consistent/global/{type}/, channel overrides at channels/{Name}/assets/{type}/, temp at channels/{Name}/active_production/{prod_id}/assets/"
  - "Asset filename convention: {type}_{hash8}_{scene_id}.{ext} for scoped assets, {type}_{hash8}.{ext} for global"
  - "Cache entry lifecycle: SET with TTL → GET validates file exists → evict_expired/orphan_cleanup → CLEAR"

requirements-completed: [PROD-VISUAL-04, PROD-VISUAL-05, PROD-VISUAL-07]

duration: 58min
completed: 2026-07-17
---

# Phase 10 Plan 01: Visual Asset Pipeline Foundation Summary

**AssetResult dataclass, BaseAssetProvider ABC, SQLite-backed AssetCache with TTL eviction, storage path helpers, search query generators, and complete test suite**

## Performance

- **Duration:** 58 min
- **Started:** 2026-07-17T04:04:02Z
- **Completed:** 2026-07-17T05:01:53Z
- **Tasks:** 3
- **Files modified:** 10

## Accomplishments

- **AssetResult dataclass** with source_url, file_extension, metadata, and score fields — mirrors TTSResult pattern from audio/tts
- **BaseAssetProvider ABC** with abstract search() and download() methods plus concrete search_and_download() convenience — cannot be instantiated directly (TypeError)
- **Two-tier storage system** with consistent_asset_path (global + channel override) and temp_asset_dir (production-scoped) per D-05/D-06/D-07
- **Content hashing** via compute_content_hash() returning deterministic 8-char SHA-256 hex digests (D-15)
- **Asset naming** via build_asset_filename() following {type}_{hash}_{scene_id}.{ext} convention (D-13/D-16)
- **SQLite-backed AssetCache** with WAL mode, threading.Lock, TTL eviction, permanent entry support, file existence validation, and orphan cleanup
- **Search query generators** with stop-word filtering for scene text → API keyword translation
- **Complete test suite** (39 tests) covering ABC instantiation guard, dataclass defaults, path resolution, content hashing, channel validation, cache CRUD, TTL expiry, file deletion detection, and Pitfall 2 mitigation

## Task Commits

Each task was committed atomically:

1. **Task 1: Foundation modules (__init__, base, storage, search)** - `a14277d` (feat)
2. **Task 2: AssetCache** - `5ac56cb` (feat)
3. **Task 3: Test fixtures and unit tests** - `b2f750a` (feat)

## Files Created

### Source (`agent_core/assets/`)
| File | Lines | Purpose |
|------|-------|---------|
| `__init__.py` | 14 | Package init exporting all public API symbols |
| `base.py` | 79 | AssetResult dataclass + BaseAssetProvider ABC |
| `storage.py` | 184 | Path resolution, content hashing, filename building, metadata sidecars |
| `cache.py` | 298 | SQLite-backed AssetCache with TTL eviction and file validation |
| `search.py` | 83 | Search query generation with stop-word filtering and SFX variants |

### Tests (`tests/test_assets/`)
| File | Lines | Purpose |
|------|-------|---------|
| `__init__.py` | 0 | Empty package init |
| `conftest.py` | 152 | Mock API response fixtures, env var isolation, temp cache fixture |
| `test_base.py` | 145 | ABC instantiation guard, AssetResult fields, search_and_download |
| `test_storage.py` | 175 | Path resolution, hashing, naming, validation |
| `test_cache.py` | 292 | Cache get/set, TTL, eviction, orphan cleanup, Pitfall 2 |

**Total:** 10 files, 1422 lines

## Decisions Made

- **Python timestamp for expiry comparison:** SQLite's `datetime('now')` has only second precision while Python's `datetime.isoformat()` has microsecond precision. Using a Python-generated timestamp for both `expires_at` storage and comparison queries ensures consistent time comparisons and correct TTL=0 expiry behavior.
- **threading.Lock over file-level portalocker:** For single-process concurrent access, `threading.Lock` + WAL mode + busy_timeout provides sufficient safety without the complexity of file-level locking (matching the pattern used by QuotaBudget).
- **File existence check on cache HIT:** Per Pitfall 2 / T-10-03, cache returns entries only if the file actually exists on disk. If missing, the entry is deleted and None returned. This prevents serving stale file references.

## Deviations from Plan

None - plan executed exactly as written.

### Adaptation Note: Verify Command Compatibility

The plan's Verify 2 command (`python -c "from agent_core.assets.cache import AssetCache; ...`) required a minor adaptation due to the Pitfall 2 mitigation (T-10-03). The command originally tried to `get()` a cache entry whose file didn't exist on disk, which the mitigation correctly returns as None. The file was pre-created before running the verify command. The implementation behavior is correct per the threat model.

## Issues Encountered

- **Microsecond precision mismatch** between Python's `datetime.isoformat()` and SQLite's `datetime('now')` — fixed by using Python timestamps for all time comparisons in the cache layer.

## Verify Commands

```
VERIFY 1 — Imports: PASSED
VERIFY 2 — Cache CRUD: PASSED
VERIFY 3 — pytest (39 tests): PASSED
```

## Next Phase Readiness

- Base provider ABC ready for Pexels/Pixabay/Freesound provider implementations (Wave 2)
- Storage helpers ready for character SVG resolution module
- Cache layer ready for provider integration (cache-aside pattern)
- Search generators ready for scene script → API keyword translation
- All 39 tests passing — foundation is solid

## Self-Check: PASSED

All 10 committed files exist. All 3 verify commands pass (imports, cache CRUD, pytest suite).

| Check | Result |
|-------|--------|
| All 10 files exist | ✅ |
| Verify 1 - Imports | ✅ |
| Verify 2 - Cache CRUD | ✅ |
| Verify 3 - pytest (39 tests) | ✅ |
| All commits exist (5/5) | ✅ |
| No accidental file deletions | ✅ |

---

*Phase: 10-visual-asset-pipeline*
*Completed: 2026-07-17*
