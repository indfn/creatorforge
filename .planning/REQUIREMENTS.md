# Requirements

## v1 Requirements

### Security & Packaging (SEC)

- [x] **SEC-01
**: Move hardcoded Gemini API key from `tts_generation.py` to `GEMINI_API_KEY` env var
- [x] **SEC-02
**: Remove `debug=True` from Flask app; add `--debug` CLI flag
- [x] **SEC-03
**: Encrypt `data/recon/.credentials` file or use system keyring; restrict perms to 0600
- [x] **SEC-04
**: Whitelist and validate allowed keys in settings API (`api_save_settings`)
- [x] **SEC-05
**: Create `pyproject.toml` with proper Python packaging (dependencies, entry points)
- [x] **SEC-06
**: Replace all `sys.path.insert(0, ...)` with proper package imports
- [x] **SEC-07
**: Remove dead `transcribe_video_openai` wrapper from `downloader.py`
- [x] **SEC-08
**: Restrict Flask to `127.0.0.1` by default; add `--host` flag for LAN access

### Test Infrastructure (TEST)

- [x] **TEST-01
**: Set up test framework with `pytest` and `pytest-cov`
- [ ] **TEST-02**: Write unit tests for scoring engine (`agent_core/scoring/engine.py`)
- [ ] **TEST-03**: Write unit tests for skeleton pipeline (`agent_core/recon/skeleton_ripper/`)
- [ ] **TEST-04**: Write unit tests for bridge module (`agent_core/recon/bridge.py`)
- [ ] **TEST-05**: Write unit tests for database models (`agent_core/recon/storage/`)
- [ ] **TEST-06**: Write unit tests for config/credential loading (`agent_core/recon/config.py`)
- [ ] **TEST-07**: Add JSON Schema validation tests for all 12 schemas
- [ ] **TEST-08**: Set up CI pipeline (GitHub Actions): lint (ruff), type-check (mypy), test (pytest)
- [ ] **TEST-09**: Add mock-based tests for YouTube Analytics fetcher (`scripts/fetch-yt-analytics.py`)
- [ ] **TEST-10**: Add mock-based tests for Instagram Insights fetcher (`scripts/fetch-ig-insights.py`)

### YouTube Publishing (PUBLISH)

- [ ] **PUBLISH-01**: Implement OAuth 2.0 token lifecycle with offline access and auto-refresh
- [ ] **PUBLISH-02**: Implement resumable YouTube upload with exponential backoff + chunked transfer; include thumbnail upload (`thumbnails.set`)
- [ ] **PUBLISH-03**: Implement QuotaBudget manager with persistent daily tracking
- [ ] **PUBLISH-04**: Generate SEO-optimized title, description, tags, category, and age rating via LLM
- [ ] **PUBLISH-05**: Support privacy status (public/private/unlisted) and `publishAt` scheduling
- [ ] **PUBLISH-06**: Generate/select thumbnail — auto-extract keyframe from video or flag for user-provided image
- [ ] **PUBLISH-07**: Integrate publishing with channel config (`channels/{Name}/channel_config.json`)
- [ ] **PUBLISH-08**: Implement dual-credential partitioning — scrapers use API-key-only project (Project A), uploads use channel-specific OAuth project (Project B) — so quota exhaustion from discovery never blocks publishing
- [ ] **PUBLISH-09**: Assign video to playlist(s) during or after upload via PlaylistItems API
- [ ] **PUBLISH-10**: Set full video metadata on upload: YouTube category, video language, recording date/location, made-for-kids flag, age restriction, license (standard vs CC), embed enabled/disabled, comments enabled/disabled
- [ ] **PUBLISH-11**: Generate chapter markers in the video description from per-scene timestamps (scene_01, scene_02, ...)
- [ ] **PUBLISH-12**: Pin a comment on the published video (e.g., timestamp links, CTA, pinned Q&A prompt)
- [ ] **PUBLISH-13**: Update video metadata post-hoc after publish (title, description, tags, thumbnail, playlist assignment)

### Channel Onboarding & Branding (CHANNEL)

- [ ] **CHANNEL-01**: Complete OAuth 2.0 flow with offline access for channel management; token per channel with auto-refresh
- [ ] **CHANNEL-02**: Set channel basic info via `channels.update` API (description, tags/keywords, country, default language)
- [ ] **CHANNEL-03**: Upload channel profile picture (avatar) via API
- [ ] **CHANNEL-04**: Upload channel banner image via API
- [ ] **CHANNEL-05**: Set channel branding watermark (appears on embedded video player)
- [ ] **CHANNEL-06**: Configure default video upload settings (visibility default, comment moderation defaults, license default, embed toggle)
- [ ] **CHANNEL-07**: Persist all channel branding config to `channels/{Name}/channel_config.json`

### Analytics & Brain Evolution (ANALYTICS)

- [ ] **ANALYTICS-01**: Implement 24h-delayed analytics collection per video (YouTube Data + Analytics APIs)
- [ ] **ANALYTICS-02**: Persist analytics entries as JSONL with proper schema
- [ ] **ANALYTICS-03**: Implement dual-phase polling — basic public metrics at 24h, deep behavioral metrics (CTR, AVD, retention) at mandatory 72h delay (YouTube Analytics requires 48-72h to stabilize)
- [ ] **ANALYTICS-04**: Implement brain weight updater: transform learning weights from performance data
- [ ] **ANALYTICS-05**: Integrate updated brain weights into scoring engine pipeline
- [ ] **ANALYTICS-06**: Implement `analytics/insights.py` aggregate functions
- [ ] **ANALYTICS-07**: Implement `analytics/brain_updater.py` evolution protocol

### Audio Production (PROD-AUDIO)

- [ ] **PROD-AUDIO-01**: Abstract TTS provider with multi-provider fallback chain (Gemini → Google Cloud TTS → Edge TTS)
- [ ] **PROD-AUDIO-02**: Implement word-level force alignment via `faster-whisper` with VAD pre-segmentation
- [ ] **PROD-AUDIO-03**: Pin `faster-whisper` version and validate alignment accuracy
- [ ] **PROD-AUDIO-04**: Per-scene TTS generation — production splits script into scenes, generates `scene_XX_audio.wav` for each
- [ ] **PROD-AUDIO-05**: Generate per-scene subtitle files from force-aligned transcript (SRT/VTT)
- [ ] **PROD-AUDIO-06**: Mark generated audio as temp asset — cleaned up after final video is published

### Visual Asset Pipeline (PROD-VISUAL)

- [ ] **PROD-VISUAL-01**: Implement Pexels API asset scraping for B-roll footage with caching
- [ ] **PROD-VISUAL-02**: Implement Pixabay API as Pexels fallback for images/video
- [ ] **PROD-VISUAL-03**: Implement Freesound API SFX scraping with content-based search
- [ ] **PROD-VISUAL-04**: Split asset storage into consistent (reusable) vs temp (per-video) — consistent at `assets/consistent/`, temp at `channels/{Name}/active_production/`
- [ ] **PROD-VISUAL-05**: Implement global consistent asset library at `assets/consistent/global/` with channel overrides at `channels/{Name}/assets/`
- [ ] **PROD-VISUAL-06**: Support character SVG models as first-class consistent assets — load, cache, reference across scenes and channels
- [ ] **PROD-VISUAL-07**: Build asset cache layer (SQLite-backed, TTL-based eviction) for consistent and stock assets
- [ ] **PROD-VISUAL-08**: Handle rate limits and API quota for all stock providers
- [ ] **PROD-VISUAL-09**: Remove unused commented-out dependencies for Pillow/matplotlib (or move to extras)

### Scene Assembly & Final Render (PROD-RENDER)

- [ ] **PROD-RENDER-01**: Production workflow splits script into numbered scenes before generation begins
- [ ] **PROD-RENDER-02**: Two-pass hybrid rendering per scene — Puppeteer rasterizes HyperFrames DOM/SVG animations frame-by-frame, FFmpeg accepts frame stream and composes scene video clip
- [ ] **PROD-RENDER-03**: Assemble all rendered scene clips into final video with crossfade transitions between scenes
- [ ] **PROD-RENDER-04**: Overlay per-scene subtitle tracks (SRT/VTT from PROD-AUDIO-05) onto corresponding scene clips
- [ ] **PROD-RENDER-05**: Support multi-format output (16:9 long-form, 9:16 Shorts, 1:1 Instagram) from assembled master
- [ ] **PROD-RENDER-06**: Clean up temp assets (per-scene audio, subtitle files, rendered clips) after final video is published
- [ ] **PROD-RENDER-07**: Move render config into `channel_config.json` per channel

### Pipeline Infrastructure (PIPE)

- [x] **PIPE-01**: Implement checkpoint artifacts between all pipeline stages (typed, schema-validated)
- [x] **PIPE-02**: Implement resume-from-checkpoint on crash/restart
- [x] **PIPE-03**: Add schema validation as quality gates at every stage boundary
- [x] **PIPE-04**: Implement QuotaBudget as a shared service consumed by all quota-aware stages
- [x] **PIPE-05**: Add file locking (`portalocker`) to tracker and state files
- [x] **PIPE-06**: Cap in-memory `active_jobs` dict with LRU eviction
- [x] **PIPE-07**: Checkpoint system supports scene-level granularity — each scene's artifacts (audio, subtitles, rendered clip) checkpoint independently for resume

---

### Agent Documentation (DOC)

- [ ] **DOC-01**: Create `AGENTS.md` (or OpenCode-equivalent) at project root describing the full pipeline workflow: discover → angle → script → produce → publish → analyze → learn, with stage inputs/outputs, available commands, and error recovery
- [ ] **DOC-02**: Create process-specific markdown files in `.agents/docs/` for each pipeline stage, documenting input contracts, output artifacts, command references, and recovery procedures

---

## v2 Requirements (Deferred)

- Multi-platform publishing (Instagram, TikTok)
- Full video editor UI
- Real-time analytics dashboard
- Advanced brain algorithms (beyond simple weight multiplication)
- Multi-language support / translation
- Custom video player UI

---

## Out of Scope

- Mobile app (iOS/Android) — not a consumer mobile product
- Full video editor (replacing human editing) — focus on automated pipeline
- TikTok/Instagram native upload — YouTube-only for v1
- Community features (comments, likes, sharing) — handled natively by platforms
- On-premise deployment — local/agentic CLI only

---

## Traceability

_(filled by roadmap)_

---

*Last updated: 2026-07-10 — added CHANNEL-01 through CHANNEL-07, PUBLISH-09 through PUBLISH-13, removed caption upload (subtitles burned into video via HyperFrames at render time)*
