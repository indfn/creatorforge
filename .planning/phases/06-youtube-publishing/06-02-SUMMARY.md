# Plan 06-02 SUMMARY

**Status:** READY_FOR_EXECUTION
**Phase:** 06-youtube-publishing
**Plan:** 02 — Metadata & SEO
**Requirements:** PUBLISH-04, PUBLISH-10
**Dependencies:** 06-01 (Upload)
**Wave:** 2

## What Was Planned

Replace stubs in `agent_core/publishing/metadata.py` with production-grade LLM-powered SEO metadata generation.

### Key Functions

| Function | Purpose |
|----------|---------|
| `generate_metadata(channel, script_data, brain_data)` → dict | Calls LLM (via `LLMClient`) with brain.json ICP/keywords + brand context → returns title, description, tags, category_id |
| `generate_chapters(scene_checkpoints)` → str | Reads scene-level checkpoints → formats `00:00 - Intro\n01:30 - ...` |
| `build_video_snippet(metadata, chapters, channel_config)` → dict | Assembles YouTube API-ready snippet dict with snippet/status/recordingDetails |
| `generate_full_metadata(channel, ...)` → dict | Convenience wrapper for programmatic callers (uploader.py) |
| `main()` CLI | `--channel`, `--dry-run`, `--description`, `--chapters-file`, `--pipeline-id` |

### Tasks

1. **Task 1:** Implement `generate_metadata()` — LLM prompt with brain context, brand tone, script structure; post-process title/tags; backward-compatible stubs
2. **Task 2:** Implement `generate_chapters()`, `build_video_snippet()`, CLI with `--dry-run`, metadata persistence

### Coverage

- **PUBLISH-04** (SEO via LLM): Fully covered — `generate_metadata()` generates title/desc/tags/category using LLM + brain.json
- **PUBLISH-10** (Full metadata on upload): Fully covered — `build_video_snippet()` sets categoryId, defaultLanguage, recordingDate, madeForKids, embed, privacy status

## Context Budget Estimate

- Task 1 (~20-25%): New LLM prompt logic, config loading, fallback handling
- Task 2 (~20-25%): Chapter parsing, snippet assembly, CLI argparsing, file persistence
- **Total: ~40-50%** — within budget

## Decision Traceability

- **D-01/D-02** (dry-run): `--dry-run` flag in CLI; used by uploader before committing
- **D-03** (metadata persistence): Written to `channels/{Name}/active_production/metadata.json`
- **D-04** (brain.json context): LLM prompt includes ICP, pillars, keywords from brain.json
- **D-05/D-06** (chapter markers from checkpoints): `generate_chapters()` reads scene-level checkpoints
- **D-07** (description/chapters-file override): `--description` and `--chapters-file` CLI flags
- **D-15** (metadata.py is the module): All functions in metadata.py
