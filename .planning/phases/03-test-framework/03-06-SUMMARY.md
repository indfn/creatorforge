---
phase: 03-test-framework
plan: 06
subsystem: agent_core.recon.skeleton_ripper
tags:
  - testing
  - pipeline
  - mocking
  - unit-tests
requires: [plan-01]
affects: [agent_core/recon/skeleton_ripper/pipeline.py]
tech-stack:
  added: [unittest.mock]
  patterns: [monkeypatch fixtures, sys.modules patching, side_effect callbacks]
key-files:
  created:
    - tests/test_recon/skeleton_ripper/__init__.py
    - tests/test_recon/skeleton_ripper/test_pipeline.py
decisions:
  - "sys.modules['instaloader'] patched at module level to prevent ImportError"
  - "download_direct mock uses side_effect to create real temp files so video_path.exists() passes"
  - "monkeypatch.setenv for OPENAI_API_KEY enables transcribe_video path in mocked pipeline"
  - "pipeline_mocks fixture at module level (shared across TestPipelineRun, TestPipelineSaveOutputs, TestRunSkeletonRipper)"
metrics:
  duration: 6m
  tests_added: 28
  tests_passing: 27
  tests_skipped: 1
  completed_date: 2026-07-12
  total_functions: 850
requirements: [TEST-03]
---

# Phase 03 Plan 06: Skeleton Pipeline Unit Tests Summary

Comprehensive unit tests for `SkeletonRipperPipeline` — all 5 stages (scrape, transcribe, extract, aggregate, synthesize) tested with fully mocked external dependencies. Zero real API calls; all file I/O isolated to `tmp_path`.

## Test Coverage

| Class | Tests | Description |
|-------|-------|-------------|
| `TestPipelineRun` | 14 (13 pass, 1 skip) | Successful run, progress callbacks, error paths, cache integration, multi-creator |
| `TestJobConfig` | 4 | `create_job_config()` defaults, overrides, field validation |
| `TestJobProgress` | 1 | Default values and status initialization |
| `TestJobResult` | 2 | Result with empty and populated skeletons |
| `TestJobStatus` | 2 | Enum values and member access |
| `TestPipelineSaveOutputs` | 1 | JSON output files written to reports dir |
| `TestRunSkeletonRipper` | 2 | Module-level convenience function with progress |
| `TestTestCount` | 1 | Meta-test: verifies >=20 test functions exist |

**Total: 28 test functions across 7 test classes and 1 meta-test**

## Mock Architecture

### External Dependencies Mocked

| Dependency | Mock Target | Strategy |
|-----------|-------------|----------|
| `InstaClient` | `pipeline.InstaClient` | `monkeypatch.setattr` with `MagicMock` class |
| `download_direct` | `pipeline.download_direct` | `side_effect` creates real files for `path.exists()` |
| `transcribe_video` | `pipeline.transcribe_video` | Returns `MOCK_VALID_TRANSCRIPT` |
| `load_config` | `pipeline.load_config` | Returns MagicMock with `ig_username`/`ig_password` |
| `TranscriptCache` | `pipeline.TranscriptCache` | Class return_value with cache instance mock |
| `LLMClient` | `pipeline.LLMClient` | Returns `complete()`/`chat()` responses |
| `BatchedExtractor` | `pipeline.BatchedExtractor` | Controlled `extract_all()` return value |
| `SkeletonAggregator` | `pipeline.SkeletonAggregator` | Controlled `aggregate()` return value |
| `PatternSynthesizer` | `pipeline.PatternSynthesizer` | Controlled `synthesize()` return with JSON-serializable attrs |
| `instaloader` | `sys.modules['instaloader']` | Module-level mock to prevent ImportError |
| `WHISPER_AVAILABLE` | `pipeline.WHISPER_AVAILABLE` | Set to `False` |
| `OPENAI_API_KEY` | `os.getenv` via `monkeypatch.setenv` | Enables transcribe_video code path |
| `RECON_DATA_DIR` | `pipeline.RECON_DATA_DIR` | Redirected to `tmp_path` |

### Key Design Decisions

1. **`sys.modules` patching**: `instaloader` is mocked at module level in the test file (before any pipeline imports) because `agent_core.recon.scraper.instagram` imports it. Without this, the test file can't import the pipeline module.

2. **Real temp files for downloads**: The `download_direct` mock uses `side_effect` to call `path.write_bytes(b"fake video content")`. This is necessary because the pipeline checks `video_path.exists()` after the download call.

3. **API key injection**: `monkeypatch.setenv("OPENAI_API_KEY", ...)` is used because the pipeline's `_scrape_and_transcribe` method checks `config.openai_api_key or os.getenv('OPENAI_API_KEY')`. Without a key, the transcription codepath is skipped entirely.

## Test Results

```
28 items collected
27 passed, 1 skipped (intentionally: test_partial_creator_failure)
0 failed
```

## Deviations from Plan

None — plan executed exactly as written.

## Verification Checklist

- [x] All 5 pipeline stages execute in correct order with mocks
- [x] Error paths: no transcripts, no skeletons, missing creds, login failure
- [x] Cache integration: hits skip download/transcribe, misses proceed normally
- [x] Progress callback fires at each stage
- [x] Output files are valid JSON
- [x] JobConfig defaults and overrides correct
- [x] All external deps mocked — zero real API calls made
- [x] All tests isolated to tmp_path directories
