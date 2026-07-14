# Phase 6: YouTube Publishing - Context

**Gathered:** 2026-07-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Videos are published with complete metadata (category, language, playlist, chapters, audience settings), SEO-optimized title/desc/tags, thumbnail, pin comment, and the ability to update everything post-hoc. Dual-credential partitioning prevents scraper quota from blocking publishes.

**Prerequisites:** Channel must be branded (Phase 5), OAuth tokens exist per-channel, QuotaBudget from Phase 1 is operational.

</domain>

<decisions>
## Implementation Decisions

### LLM metadata: Inline with --dry-run flag
- **D-01:** `upload_video()` generates SEO metadata (title, desc, tags, category) + uploads in one command by default
- **D-02:** `--dry-run` flag displays generated metadata without uploading — user can review and confirm
- **D-03:** Generated metadata persisted to `channels/{Name}/active_production/metadata.json`
- **D-04:** Metadata LLM call uses brain.json context (ICP, pillars, keywords) for on-brand generation

### Chapter markers: Auto-generated from checkpoint timestamps
- **D-05:** Uploader reads scene-level checkpoints from `data/checkpoints/{pipeline_id}/` to build chapter timestamps
- **D-06:** Format: `00:00 - Intro\n01:30 - Scene 2\n...` appended to description
- **D-07:** User can override via `--description` or `--chapters-file` flags

### Playlist management: Assign only by default, --ensure-playlist for creation
- **D-08:** Uploader reads `channel_config.json["playlists"]` for target playlist IDs
- **D-09:** If playlist ID not found, print warning — skip assignment, continue upload
- **D-10:** `--ensure-playlist "name"` flag creates the playlist if missing

### Quota UX: Pre-flight check with display
- **D-11:** Before upload, `QuotaBudget.can_consume("youtube_upload", 1)` — remaining quota displayed
- **D-12:** On quota exhausted: `"Remaining upload quota: 0/6 today. Resets at midnight UTC."`
- **D-13:** On `HttpError(403, "quotaExceeded")` mid-upload: catch, log, return failure

### Implementation architecture
- **D-14:** `agent_core/publishing/uploader.py` is the main module — resumable upload, chunked transfer, thumbnail
- **D-15:** `agent_core/publishing/metadata.py` — LLM-based SEO generation
- **D-16:** `agent_core/publishing/scheduler.py` — peak-time scheduling (basic stub, advanced in future)
- **D-17:** Chapter markers, pin comment, playlist assignment are functions in `uploader.py` (or a `post_publish.py` helper)
- **D-18:** All API calls use `get_authenticated_service()` from Phase 5's OAuth core module
- **D-19:** QuotaBudget `consume()` called after successful upload to decrement budget
- **D-20:** Dual-credential: scripts that scrape (Project A) are separate from upload scripts (Project B) — enforced by config

</decisions>

<canonical_refs>
## Canonical References

### Phase Requirements
- `.planning/REQUIREMENTS.md` — PUBLISH-01 through PUBLISH-13
- `.planning/ROADMAP.md` — Phase 6 goal, success criteria

### Existing Implementation
- `agent_core/publishing/uploader.py` — Upload stub (ChunkedVideoUpload)
- `agent_core/publishing/metadata.py` — Metadata stubs
- `agent_core/publishing/scheduler.py` — Scheduler stubs
- `agent_core/publishing/oauth.py` — Phase 5 OAuth core (get_authenticated_service)
- `agent_core/core/quota.py` — QuotaBudget (consume, can_consume)
- `channels/ChannelA/channel_config.json` — Config shape reference
- `schemas/channel-config.schema.json` — Updated schema (Phase 5)

### Architecture References
- `.planning/codebase/ARCHITECTURE.md`
- `.planning/codebase/INTEGRATIONS.md` — YouTube API integration details
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `agent_core/publishing/oauth.py` — `get_authenticated_service(channel)` for all YouTube API calls
- `agent_core/core/quota.py` — `QuotaBudget.can_consume("youtube_upload", 1)` pre-flight
- `agent_core/core/checkpoint.py` — `CheckpointManager` scene-level checkpoints for chapter timestamps
- `channels/{Name}/channel_config.json` — `youtube` section with oauth_token_path, upload_defaults

### Integration Points
- Upload flow: render complete → `channels/{Name}/active_production/render/final_video.mp4` → upload via `resumable` protocol
- Metadata: generated here → persisted to `channels/{Name}/active_production/metadata.json` → consumed by Phase 7 (analytics)
- Chapter markers: scene checkpoints from Phase 1 → description format
</code_context>

<specifics>
- `google-api-python-client` MediaFileUpload with `resumable=True` handles chunked upload automatically
- Thumbnail upload via `youtube.thumbnails().set(videoId=..., media_body=...)`
- Pin comment via `youtube.commentThreads().insert(part="snippet", body={...})`
- Post-hoc update via `youtube.videos().update(part="snippet,status", body={...})`
</specifics>

<deferred>
None — discussion stayed within phase scope.
</deferred>

---

*Phase: 06-youtube-publishing*
*Context gathered: 2026-07-13*
