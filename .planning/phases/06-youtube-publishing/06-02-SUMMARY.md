---
phase: 06-youtube-publishing
plan: 02
type: execute
wave: 2
subsystem: publishing
tags: [metadata, seo, youtube, chapters, llm, cli]
requires: [06-01, channel-config, brain-json]
provides: [metadata-generation, chapter-generation, video-snippet]
affects: [uploader, analytics-phase-7]
requirements: [PUBLISH-04, PUBLISH-10]
tech-stack:
  added: [argparse, datetime, re, pathlib, LLMClient]
  patterns: [template-method-metadata, llm-with-fallback, cli-dry-run]
key-files:
  created:
    - agent_core/publishing/metadata.py
  modified: []
decisions:
  - "Template-based fallback when LLM API key not configured — deterministic metadata from script_data + brain_data"
  - "generate_chapters accepts pre-loaded dicts (not coupled to CheckpointManager) — testable, CLI loads via pipeline-id"
  - "Backward-compatible stubs (generate_title/description/tags) delegate to generate_metadata"
  - "Full description assembled as body + chapters section + CTA footer in build_video_snippet"
  - "metadata.json persists only on --save or non-dry-run; --dry-run prints JSON to stdout"
metrics:
  duration: 15m
  completed_date: "2026-07-14"
  tasks: 2
  files: 1
  commits: 1
---

# Phase 06 Plan 02: SEO Metadata & Video Snippet Builder Summary

**One-liner:** Full SEO metadata generation engine with LLM-powered titles/descriptions/tags, YouTube chapter markers from scene checkpoints, CLI with `--dry-run` preview, and YouTube API video snippet assembly covering all PUBLISH-10 fields.

## Overview

Implemented the complete `agent_core/publishing/metadata.py` module (1,053 lines), replacing three `NotImplementedError` stubs with a production-quality metadata generation pipeline:

| Function | Purpose |
|----------|---------|
| `generate_metadata()` | SEO metadata using LLM (or template fallback): title, description, tags, category_id |
| `generate_chapters()` | `00:00 - Label` format from scene checkpoint data |
| `build_video_snippet()` | YouTube API dict with snippet + status + recordingDetails |
| `generate_full_metadata()` | Convenience wrapper for programmatic callers (uploader.py) |
| `generate_title()` / `generate_description()` / `generate_tags()` | Backward-compatible stubs delegating to `generate_metadata()` |
| `main()` | CLI with `--channel`, `--dry-run`, `--save`, `--description`, `--chapters-file`, `--pipeline-id` |

### Key Design Decisions

1. **LLM-first with template fallback**: Uses `LLMClient.chat()` with structured prompts containing brain.json ICP/pillars/keywords and brand tone. Falls back to deterministic template generation when LLM not configured or API call fails.

2. **Testable checkpoint decoupling**: `generate_chapters()` accepts pre-loaded list of dicts rather than coupling to `CheckpointManager` directly. CLI uses `--pipeline-id` to bridge the two when needed.

3. **PUBLISH-10 compliance**: The snippet dict covers all required YouTube API fields — `categoryId`, `defaultLanguage`, `defaultAudioLanguage`, `recordingDate`, `selfDeclaredMadeForKids`, `embeddable`, `privacyStatus`, `publishAt`.

4. **CLI-first UX**: `--dry-run` prints JSON snippet to stdout, `--save` persists metadata.json alongside it. Overrides available via `--description` and `--chapters-file`.

### Threat Model Compliance

- **T-06-02-01 (Info Disclosure)**: LLM prompt uses brain ICP/pillars/keywords only — no PII or credentials. Uses existing `LLMClient` which does not log prompt contents.
- **T-06-02-03 (Spoofing)**: Category ID enforced via `YOUTUBE_CATEGORY_IDS` dict lookup only; unknown categories default to "27" (Education).
- **T-06-02-02 (Tampering)**, **T-06-02-04 (Info Disclosure)**, **T-06-02-05 (Repudiation)**: Accepted per threat model — local-only writes, dry-run stdout intended behavior, no audit trail needed.

## Deviations from Plan

None — plan executed exactly as written.

## Verification Results

| Check | Result |
|-------|--------|
| `ruff check metadata.py` | PASSED (0 errors) |
| `mypy metadata.py` | PASSED (0 errors in metadata.py; 13 pre-existing in other files) |
| All imports clean | PASSED |
| `generate_metadata()` structure | PASSED (title < 100 chars, tags < 500 chars, valid category ID) |
| `generate_chapters()` format | PASSED (00:00 format, empty input → "") |
| `build_video_snippet()` fields | PASSED (all PUBLISH-10 fields present) |
| `generate_full_metadata()` flow | PASSED (real data loads, correct title/description/chapters) |
| CLI `--dry-run` flag | PASSED (JSON output, no persistence without --save) |
| CLI `--help` | PASSED (lists all flags including --dry-run) |

## Self-Check: PASSED

- `agent_core/publishing/metadata.py` exists and is 1,053 lines (plan min_lines: 200) ✓
- Module imports cleanly ✓
- All six public functions importable ✓
- Backward-compatible stubs work ✓
- CLI works with `--help` and `--dry-run` ✓
