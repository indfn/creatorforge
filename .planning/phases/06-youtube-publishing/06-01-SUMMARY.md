---
phase: 06-youtube-publishing
plan: 01
plan_type: execute
status: READY_FOR_EXECUTION
created: 2026-07-14
wave: 1
autonomous: true
requirements:
  - PUBLISH-02
  - PUBLISH-05
  - PUBLISH-06
  - PUBLISH-07
---

# Plan 06-01: Upload Engine — READY_FOR_EXECUTION

**Objective:** Implement `agent_core/publishing/uploader.py` with resumable YouTube upload, thumbnail upload, status updates, quota integration, and a CLI entry point.

## What This Plan Delivers

1. **`upload_video(channel, video_path, thumbnail_path=None, privacy="private", publish_at=None) -> str | None`**
   - Resumable upload via `MediaFileUpload(chunksize=256*1024, resumable=True)`
   - Full video body with snippet (title, categoryId, defaultLanguage) and status (privacy, publishAt, madeForKids, embeddable, license)
   - Exponential backoff on retryable server errors (max 5 attempts)
   - `HttpError(403, "quotaExceeded")` caught — returns None
   - Pre-flight `QuotaBudget.can_consume()` check; post-success `consume()` call
   - Reads channel_config.json for defaults (category, language, privacy, license, embed)

2. **`upload_thumbnail(channel, video_id, thumbnail_path) -> bool`**
   - `youtube.thumbnails().set()` call with `MediaFileUpload`

3. **`set_video_status(channel, video_id, privacy, publish_at=None) -> bool`**
   - Updates snippet + status of already-uploaded video

4. **CLI entry point**
   - `--channel` (required), `--video`, `--thumbnail`, `--privacy`, `--schedule`, `--dry-run`
   - Default privacy from channel_config.json
   - Pre-flight quota display
   - `--dry-run` flag (per D-02) for metadata review without uploading

## Tasks

| # | Task | Type | Key Actions |
|---|------|------|-------------|
| 1 | Core upload functions | auto | `upload_video`, `upload_thumbnail`, `set_video_status` with exponential backoff, quota integration, channel config reading |
| 2 | CLI entry point | auto | argparse with all flags, config loading, pre-flight display, --dry-run |

## Dependencies

- **Depends on:** Phase 5 (OAuth module — `get_authenticated_service()`)
- **Depends on:** Phase 1 (QuotaBudget — `can_consume()` / `consume()`)

## Key Decisions Implemented

| Decision | Implementation |
|----------|---------------|
| D-11 | Pre-flight `QuotaBudget.can_consume("youtube_upload", 1)` before upload |
| D-12 | "Remaining upload quota: X/6 today" display |
| D-13 | `HttpError(403, "quotaExceeded")` caught mid-upload |
| D-14 | uploader.py as main module with resumable + chunked |
| D-18 | All API calls via `get_authenticated_service()` from oauth.py |
| D-19 | `QuotaBudget.consume("youtube_upload")` after success |
| D-20 | Channel config per-channel (auth partitioning by config) |
| D-02 | `--dry-run` flag to preview without upload |
