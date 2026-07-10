# Requirements

## v1 Requirements

### Security & Packaging (SEC)

- [ ] **SEC-01**: Move hardcoded Gemini API key from `tts_generation.py` to `GEMINI_API_KEY` env var
- [ ] **SEC-02**: Remove `debug=True` from Flask app; add `--debug` CLI flag
- [ ] **SEC-03**: Encrypt `data/recon/.credentials` file or use system keyring; restrict perms to 0600
- [ ] **SEC-04**: Whitelist and validate allowed keys in settings API (`api_save_settings`)
- [ ] **SEC-05**: Create `pyproject.toml` with proper Python packaging (dependencies, entry points)
- [ ] **SEC-06**: Replace all `sys.path.insert(0, ...)` with proper package imports
- [ ] **SEC-07**: Remove dead `transcribe_video_openai` wrapper from `downloader.py`
- [ ] **SEC-08**: Restrict Flask to `127.0.0.1` by default; add `--host` flag for LAN access

### Test Infrastructure (TEST)

- [ ] **TEST-01**: Set up test framework with `pytest` and `pytest-cov`
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

### Analytics & Brain Evolution (ANALYTICS)

- [ ] **ANALYTICS-01**: Implement 24h-delayed analytics collection per video (YouTube Data + Analytics APIs)
- [ ] **ANALYTICS-02**: Persist analytics entries as JSONL with proper schema
- [ ] **ANALYTICS-03**: Implement cross-channel insight aggregation and pattern detection
- [ ] **ANALYTICS-04**: Implement brain weight updater: transform learning weights from performance data
- [ ] **ANALYTICS-05**: Integrate updated brain weights into scoring engine pipeline
- [ ] **ANALYTICS-06**: Implement `analytics/insights.py` aggregate functions
- [ ] **ANALYTICS-07**: Implement `analytics/brain_updater.py` evolution protocol

### Audio Production (PROD-AUDIO)

- [ ] **PROD-AUDIO-01**: Abstract TTS provider with multi-provider fallback chain (Gemini → Google Cloud TTS → Edge TTS)
- [ ] **PROD-AUDIO-02**: Implement word-level force alignment via `faster-whisper` with VAD pre-segmentation
- [ ] **PROD-AUDIO-03**: Pin `faster-whisper` version and validate alignment accuracy
- [ ] **PROD-AUDIO-04**: Integrate aligned transcript with scene timing for caption rendering

### Visual Asset Pipeline (PROD-VISUAL)

- [ ] **PROD-VISUAL-01**: Implement Pexels API asset scraping for B-roll footage with caching
- [ ] **PROD-VISUAL-02**: Implement Pixabay API as Pexels fallback for images/video
- [ ] **PROD-VISUAL-03**: Implement Freesound API SFX scraping with content-based search
- [ ] **PROD-VISUAL-04**: Build asset cache layer (SQLite-backed, TTL-based eviction)
- [ ] **PROD-VISUAL-05**: Handle rate limits and API quota for all stock providers
- [ ] **PROD-VISUAL-06**: Remove unused commented-out dependencies for Pillow/matplotlib (or move to extras)

### Video Rendering (PROD-RENDER)

- [ ] **PROD-RENDER-01**: Implement single-pass FFmpeg compositor using filter_complex
- [ ] **PROD-RENDER-02**: Support multi-format output (16:9 long-form, 9:16 Shorts, 1:1 Instagram)
- [ ] **PROD-RENDER-03**: Integrate TTS audio + captions + visual assets into final render
- [ ] **PROD-RENDER-04**: Build scene template renderer (text overlays, transitions)
- [ ] **PROD-RENDER-05**: Move render config into `channel_config.json` per channel

### Pipeline Infrastructure (PIPE)

- [ ] **PIPE-01**: Implement checkpoint artifacts between all pipeline stages (typed, schema-validated)
- [ ] **PIPE-02**: Implement resume-from-checkpoint on crash/restart
- [ ] **PIPE-03**: Add schema validation as quality gates at every stage boundary
- [ ] **PIPE-04**: Implement QuotaBudget as a shared service consumed by all quota-aware stages
- [ ] **PIPE-05**: Add file locking (`portalocker`) to tracker and state files
- [ ] **PIPE-06**: Cap in-memory `active_jobs` dict with LRU eviction

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

| REQ-ID | Phase | Verified | Notes |
|--------|-------|----------|-------|
| PIPE-01 | Phase 1 | Pending | Checkpoint artifacts between all pipeline stages |
| PIPE-02 | Phase 1 | Pending | Resume-from-checkpoint on crash/restart |
| PIPE-03 | Phase 1 | Pending | Schema validation as quality gates at stage boundaries |
| PIPE-04 | Phase 1 | Pending | QuotaBudget as shared service for all quota-aware stages |
| PIPE-05 | Phase 1 | Pending | File locking via portalocker for tracker/state files |
| PIPE-06 | Phase 1 | Pending | Cap active_jobs dict with LRU eviction |
| SEC-01 | Phase 2 | Pending | Move hardcoded Gemini API key to env var |
| SEC-02 | Phase 2 | Pending | Remove debug=True; add --debug CLI flag |
| SEC-03 | Phase 2 | Pending | Encrypt credential storage; restrict perms to 0600 |
| SEC-04 | Phase 2 | Pending | Whitelist and validate allowed keys in settings API |
| SEC-05 | Phase 2 | Pending | Create pyproject.toml with proper packaging |
| SEC-06 | Phase 2 | Pending | Replace sys.path hacks with proper imports |
| SEC-07 | Phase 2 | Pending | Remove dead transcribe_video_openai wrapper |
| SEC-08 | Phase 2 | Pending | Restrict Flask to 127.0.0.1 by default; --host flag |
| TEST-01 | Phase 3 | Pending | Set up pytest and pytest-cov |
| TEST-02 | Phase 3 | Pending | Unit tests for scoring engine |
| TEST-03 | Phase 3 | Pending | Unit tests for skeleton pipeline |
| TEST-04 | Phase 3 | Pending | Unit tests for bridge module |
| TEST-05 | Phase 3 | Pending | Unit tests for database models |
| TEST-06 | Phase 3 | Pending | Unit tests for config/credential loading |
| TEST-07 | Phase 4 | Pending | JSON Schema validation tests for all 12 schemas |
| TEST-08 | Phase 4 | Pending | CI pipeline: lint, type-check, test |
| TEST-09 | Phase 4 | Pending | Mock-based tests for YouTube Analytics fetcher |
| TEST-10 | Phase 4 | Pending | Mock-based tests for Instagram Insights fetcher |
| PUBLISH-01 | Phase 5 | Pending | OAuth 2.0 token lifecycle with offline access |
| PUBLISH-02 | Phase 5 | Pending | Resumable upload with exponential backoff |
| PUBLISH-03 | Phase 5 | Pending | QuotaBudget manager for publishing pipeline |
| PUBLISH-04 | Phase 5 | Pending | SEO-optimized title, description, tags via LLM |
| PUBLISH-05 | Phase 5 | Pending | Privacy status and publishAt scheduling |
| PUBLISH-06 | Phase 5 | Pending | Channel config integration |
| ANALYTICS-01 | Phase 6 | Pending | 24h-delayed analytics collection per video |
| ANALYTICS-02 | Phase 6 | Pending | Persist analytics as JSONL with schema |
| ANALYTICS-06 | Phase 6 | Pending | Analytics aggregate functions |
| ANALYTICS-03 | Phase 7 | Pending | Cross-channel insight aggregation |
| ANALYTICS-04 | Phase 7 | Pending | Brain weight updater from performance data |
| ANALYTICS-05 | Phase 7 | Pending | Integrate brain weights into scoring engine |
| ANALYTICS-07 | Phase 7 | Pending | Brain evolution protocol |
| PROD-AUDIO-01 | Phase 8 | Pending | TTS provider with multi-provider fallback |
| PROD-AUDIO-02 | Phase 8 | Pending | Word-level force alignment via faster-whisper |
| PROD-AUDIO-03 | Phase 8 | Pending | Pin faster-whisper; validate alignment accuracy |
| PROD-AUDIO-04 | Phase 8 | Pending | Integrate aligned transcript with scene timing |
| PROD-VISUAL-01 | Phase 9 | Pending | Pexels API B-roll scraping with caching |
| PROD-VISUAL-02 | Phase 9 | Pending | Pixabay API as Pexels fallback |
| PROD-VISUAL-03 | Phase 9 | Pending | Freesound API SFX scraping |
| PROD-VISUAL-04 | Phase 9 | Pending | SQLite-backed asset cache with TTL eviction |
| PROD-VISUAL-05 | Phase 9 | Pending | Rate limit and quota handling for stock APIs |
| PROD-VISUAL-06 | Phase 9 | Pending | Remove unused deps or move to extras |
| PROD-RENDER-01 | Phase 10 | Pending | Single-pass FFmpeg filter_compositor |
| PROD-RENDER-02 | Phase 10 | Pending | Multi-format output (16:9, 9:16, 1:1) |
| PROD-RENDER-03 | Phase 10 | Pending | Integrate audio + captions + visuals into render |
| PROD-RENDER-04 | Phase 10 | Pending | Scene template renderer (overlays, transitions) |
| PROD-RENDER-05 | Phase 10 | Pending | Per-channel render config in channel_config.json |

---

*Last updated: 2026-07-10 after research*
