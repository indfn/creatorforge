# CreatorForge

**AI-powered content creation suite for OpenCode/Claude Code.**

Publishes winning content by discovering competitor patterns, generating scripts, producing video, and learning from performance — all through agent commands.

---

## Core Value

One command from idea to published video: discover competitor patterns → generate script → produce video → publish → learn from results.

## Current State

**Working:**
- Competitor scraping (Instagram via Instaloader, YouTube via yt-dlp)
- LLM-based skeleton analysis and pattern extraction
- Topic scoring engine (4-criteria: ICP relevance, timeliness, content gap, proof potential)
- TTS audio generation (Gemini 3.1 Flash)
- YouTube Analytics fetch (Data API + Analytics API)
- Instagram Insights fetch (Graph API)
- PDF lead magnet generation
- Recon Flask UI (competitor management dashboard)
- Agent commands structure (`.agents/commands/viral-*.md`)

**Not Working (stubs):**
- YouTube upload + OAuth lifecycle (`agent_core/publishing/` — all stubs)
- Analytics collection + brain evolution loop (`agent_core/analytics/` — all stubs)
- Visual asset generation (`production/VisualGeneration/` — all stubs)
- Force alignment for caption syncing (`production/AudioGeneration/force_align.py` — stub)
- Full hyperframe rendering pipeline
- Production-grade security (hardcoded API key, `debug=True`, plaintext creds)
- Tests (zero tests in core modules)
- Proper packaging (no `pyproject.toml`, `sys.path` hacks)

## Constraints

- Python 3.10+ / Node.js 18+
- OpenAI-compatible LLM endpoints (`{PROVIDER}_BASE_URL`, `{PROVIDER}_API_KEY`, `{PROVIDER}_MODEL`)
- Google YouTube Data API v3 + Analytics API (OAuth)
- Google Gemini TTS (local proxy)
- Instagram via Instaloader (fragile — ToS-bound)
- TTS script untouched (custom Gemini endpoint, no changes allowed)
- `scene` and `context` are dynamic per-scene, not stored in channel config
- HyperFrames generates HTML/SVG/CSS animations — renders via Puppeteer headless browser to FFmpeg frame pipe, not native FFmpeg filter filters

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Agent manifest lives in `.agents/` | Single canonical source, symlinks for CLI-specific dirs | Done |
| Pipeline architecture | 5-stage lifecycle with brain feedback loop | Done |
| JSON Schema contracts | Validate inter-module data shapes | Done |
| Multi-channel isolation | `channels/{Name}/` per-channel config + brain | Done |
| OpenAI-compatible LLM pattern | Works with any provider via env vars | Done |
| Dual-credential YouTube access | Scraping (API key, Project A) isolated from Publishing (OAuth, Project B) | Phase 5 |
| Two-pass hybrid rendering | Puppeteer rasterizes HyperFrames DOM/CSS → FFmpeg composes with audio | Phase 10 |
| Dual-phase analytics polling | Basic metrics at 24h, deep behavioral metrics at 72h (YouTube stabilization window) | Phase 6 |
| HyperFrames as animation backbone | HTML/SVG/CSS keyframe animations rasterized via headless browser, not native FFmpeg filters | Phase 10 |
| Scene-by-scene production | Full script split into numbered scenes; each scene generates audio, subtitles, and render independently before final assembly | Phases 8-10 |
| Consistent vs temp asset separation | Reusable assets (images, SFX, character SVGs) in `assets/consistent/`; per-video generated assets in temp, cleaned after publish | Phase 9 |
| Per-scene subtitle generation | Subtitles generated per-scene during audio production, not during final render — reduces final assembly processing load | Phase 10 |
| Global + channel asset library | Global consistent assets at `assets/consistent/global/` with per-channel overrides at `channels/{Name}/assets/` | Phase 9 |
| Agent documentation first-class | AGENTS.md + process-specific docs for any AI CLI to orchestrate the pipeline | Phase 11 |

---

## Requirements

### Validated (existing)

- ✓ **RECON-01**: Scrape competitor content from Instagram — `agent_core/recon/scraper/instagram.py`
- ✓ **RECON-02**: Fetch YouTube channel videos — `agent_core/recon/scraper/youtube.py`
- ✓ **RECON-03**: Transcribe video audio via Whisper API/local — `agent_core/recon/scraper/downloader.py`
- ✓ **RECON-04**: Extract content skeletons via LLM — `agent_core/recon/skeleton_ripper/`
- ✓ **RECON-05**: Score topics against agent brain ICP — `agent_core/scoring/engine.py`
- ✓ **RECON-06**: Generate PDF lead magnets from scripts — `scripts/generate-pdf.py`
- ✓ **RECON-07**: Browse competitor data via web UI — `agent_core/recon/web/app.py`
- ✓ **PROD-01**: Generate TTS audio from scripts — `production/AudioGeneration/tts_generation.py`
- ✓ **ANALYTICS-01**: Fetch YouTube video analytics — `scripts/fetch-yt-analytics.py`
- ✓ **ANALYTICS-02**: Fetch Instagram post insights — `scripts/fetch-ig-insights.py`
- ✓ **AGENT-01**: Agent commands discoverable at `.agents/commands/viral-*.md`
- ✓ **AGENT-02**: Skills discoverable at `.agents/skills/` (23+ skills)

### Active (to build)

- CHANNEL-01: OAuth for channel management with auto-refresh
- CHANNEL-02: Set channel description, tags, country, language via API
- CHANNEL-03: Upload channel profile picture
- CHANNEL-04: Upload channel banner image
- CHANNEL-05: Set channel branding watermark
- CHANNEL-06: Configure default upload settings (visibility, comments, license)
- CHANNEL-07: Persist channel branding config to channel_config.json
- PUBLISH-01: Upload video to YouTube with metadata — uploader, OAuth, scheduling
- PUBLISH-02: Generate SEO-optimized titles, descriptions, tags
- PUBLISH-09: Assign video to playlists via PlaylistItems API
- PUBLISH-10: Set full metadata (category, language, made-for-kids, license, etc.)
- PUBLISH-11: Generate chapter markers in description from scene timestamps
- PUBLISH-12: Pin comment on published video
- PUBLISH-13: Update video metadata post-hoc
- ANALYTICS-03: Collect and persist performance data per video
- ANALYTICS-04: Aggregate cross-channel insights and detect patterns
- ANALYTICS-05: Auto-evolve brain learning weights from performance data
- PROD-02: Fetch B-roll footage from stock APIs
- PROD-03: Fetch sound effects from stock APIs
- PROD-04: Word-level force alignment for caption syncing
- PROD-05: Render full video with hyperframe scenes
- SEC-01: Move hardcoded API key to environment variable
- SEC-02: Disable Flask debug mode in production
- SEC-03: Encrypt credential storage
- SEC-04: Validate and sanitize settings API
- QUALITY-01: Add test suite for scoring engine
- QUALITY-02: Add test suite for skeleton pipeline
- QUALITY-03: Add integration tests for external API callers
- QUALITY-04: Add property-based tests for schemas
- QUALITY-05: Set up CI pipeline (lint, type-check, test)
- PACKAGE-01: Create pyproject.toml with proper packaging
- PACKAGE-02: Replace sys.path hacks with proper imports

### Out of Scope

- Cross-platform mobile app — web UI only
- TikTok/Reddit publishing — YouTube/Instagram only for v1

---

## Evolution

This document evolves at phase transitions and milestone boundaries.

---

*Last updated: 2026-07-10 — added Channel Onboarding phase, expanded Publishing phase (playlist, full metadata, chapters, pin comment, post-hoc updates)*
