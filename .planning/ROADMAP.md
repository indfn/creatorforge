# CreatorForge Roadmap

**Core Value:** One command from idea to published video: discover competitor patterns → generate script → produce video → publish → learn from results.

---

## Phases

- [x] **Phase 1: Foundation & Pipeline Infrastructure** — Build checkpoint system, quality gates, QuotaBudget service, and state management that every other phase depends on
- [x] **Phase 2: Security Hardening & Packaging** — Fix all known security vulnerabilities and properly package the project as a pip-installable module ✓
- [x] **Phase 3: Test Framework & Core Unit Tests** — Set up pytest and write comprehensive unit tests for existing core logic modules ✓
- [x] **Phase 4: CI Pipeline & Extended Tests** — Add schema validation tests, mock-based API tests, and GitHub Actions automation
- [x] **Phase 5: Channel Onboarding & Branding** — Link a YouTube channel via OAuth, set channel description/tags, upload avatar/banner/watermark, and configure default upload settings so the channel is ready for content
- [x] **Phase 6: YouTube Publishing** — Upload videos with full metadata (category, language, playlist, chapters, audience settings), SEO title/desc/tags, thumbnail, pin comment, and post-hoc updates ✓
- [x] **Phase 7: Analytics Collection & Storage** — On-demand dual-phase collection (24h basic + 72h deep), schema-validated persistence ✓
- [x] **Phase 8: Brain Evolution Loop** — Evolve agent brain learning weights from real performance data to close the content strategy feedback loop ✓
- [x] **Phase 9: Audio Production (Per-Scene)** — Per-scene TTS → per-scene force alignment (Groq API / faster-whisper) → per-scene subtitle generation → script files rewritten inline with timestamps ✓
- [x] **Phase 10: Visual Asset Pipeline** — Stock API sourcing (Pexels/Pixabay/Freesound), character SVGs, global + per-channel consistent asset library, SQLite-backed asset cache with TTL eviction ✓
- [x] **Phase 11: Scene Assembly & Final Render** — Per-scene two-pass render (HyperFrames GSAP compositions → Playwright → FFmpeg) → assembly with subtitles + crossfade transitions → multi-format output (16:9 / 9:16 / 1:1) → temp cleanup ✓
- [ ] **Phase 12: Recon Efficiency Rework** — Caption-first YouTube pipeline (no download for captioned videos), Instagram caption-as-transcript, Groq transcription provider, SQLite-backed transcript cache, transcript cleaning
- [ ] **Phase 13: Agent Documentation** — Write AGENTS.md workflow directives and process-specific markdown files for agentic automation

---

## Phase Details

### Phase 1: Foundation & Pipeline Infrastructure
**Goal**: Pipeline stages can produce typed, schema-validated checkpoint artifacts (including scene-level), resume from crashes, share the QuotaBudget service safely, and support dual-credential partitioning (scraping vs publishing).
**Depends on**: Nothing
**Requirements**: PIPE-01, PIPE-02, PIPE-03, PIPE-04, PIPE-05, PIPE-06, PIPE-07
**Non-requirement action**: Kick off Google OAuth consent screen audit and YouTube API quota extension request (2-4 week lead time — must start immediately to avoid blocking Phase 5)
**Completed**: 2026-07-12 — 3 plans, 7/7 PIPE requirements
**Success Criteria** (what must be TRUE):
  1. Every pipeline stage produces a typed JSON artifact validated against its JSON Schema contract
  2. Pipeline can resume from the last successful checkpoint after a crash or restart without re-running completed stages
  3. Checkpoint system supports scene-level granularity — each scene's artifacts (audio, subtitles, rendered clip) checkpoint independently
  4. QuotaBudget shared service tracks daily quota consumption per API and rejects requests when budget is exhausted
  5. State management supports separate credential loading for scraping projects (API Key) and channel publishing projects (OAuth 2.0)
  6. State files use file locking via `portalocker` to prevent concurrent access corruption
  7. In-memory `active_jobs` dict uses LRU eviction with a configurable maximum capacity
**Plans**: 3 plans
**Completed**: 2026-07-12 — 3 plans, 7/7 PIPE requirements

### Phase 2: Security Hardening & Packaging
**Goal**: All known security vulnerabilities are fixed and the project is properly packaged as a pip-installable module with zero `sys.path` hacks.
**Depends on**: Phase 1
**Requirements**: SEC-01, SEC-02, SEC-03, SEC-04, SEC-05, SEC-06, SEC-07, SEC-08
**Success Criteria** (what must be TRUE):
   1. No hardcoded API keys or proxy URLs in source code — all credentials read from environment variables (`GEMINI_API_KEY`, `PROXY_URL`)
   2. Flask app runs with `debug=False` by default; `--debug` CLI flag enables development mode
   3. Credential storage uses encryption or system keyring with file permissions restricted to `0600`
   4. Settings API rejects requests with keys outside a defined whitelist and validates value formats before saving
   5. Project installs via `pip install -e .` using `pyproject.toml`; zero `sys.path.insert` hacks remain
   6. Flask binds to `127.0.0.1` by default; `--host` flag enables explicit LAN access
**Plans**: 3 plans
**Completed**: 2026-07-12 — 3 plans, 8/8 SEC requirements

Plans:
- [x] 02-01-PLAN.md — Packaging + credential env vars + dead code removal
- [x] 02-02-PLAN.md — Fernet credential encryption with 0600 perms
- [x] 02-03-PLAN.md — Flask hardening (debug/host/settings) + sys.path cleanup

### Phase 3: Test Framework & Core Unit Tests
**Goal**: Core business logic modules (scoring engine, skeleton pipeline, bridge, storage, config) have comprehensive unit test coverage with pytest.
**Depends on**: Phase 2
**Requirements**: TEST-01, TEST-02, TEST-03, TEST-04, TEST-05, TEST-06
**Success Criteria** (what must be TRUE):
   1. `pytest` and `pytest-cov` are configured; `pytest` from project root discovers and runs all tests with coverage reporting
   2. Scoring engine tests cover all 4 criteria (ICP relevance, timeliness, content gap, proof potential) and weighted total calculation with edge cases
   3. Skeleton pipeline tests cover all 5 stages (scrape, transcribe, extract, aggregate, synthesize) using mock data
   4. Bridge module tests cover skeleton-to-topic conversion, pillar matching, and engagement extraction from varied formats
   5. Database model tests cover CRUD operations for Asset and Collection with type validation and error cases
   6. Config/credential loading tests cover environment variable cascade (env → .env → .credentials) and credential masking
**Plans**: 6 plans
**Completed**: 2026-07-12 — 6 plans, 6/6 TEST requirements

Plans:
- [x] 03-01-PLAN.md — pytest setup + conftest.py (TEST-01)
- [x] 03-02-PLAN.md — Scoring engine unit tests (TEST-02)
- [x] 03-03-PLAN.md — Config/credential loading tests (TEST-06)
- [x] 03-04-PLAN.md — Bridge module tests (TEST-04)
- [x] 03-05-PLAN.md — Database model tests (TEST-05)
- [x] 03-06-PLAN.md — Skeleton pipeline tests (TEST-03)

### Phase 4: CI Pipeline & Extended Tests
**Goal**: Schema validation tests, external API mock tests, and automated CI pipeline ensure code quality gates are enforced on every change.
**Depends on**: Phase 3
**Requirements**: TEST-07, TEST-08, TEST-09, TEST-10
**Success Criteria** (what must be TRUE):
   1. All 15 JSON Schema files have validation tests: valid fixtures pass, known-invalid fixtures are properly rejected
   2. GitHub Actions CI pipeline runs ruff lint, mypy type-check, and pytest on every push and pull request
   3. YouTube Analytics fetcher uses mocks to verify API response parsing, quota handling, and error recovery
   4. Instagram Insights fetcher uses mocks to verify API response parsing, token refresh, and error recovery
**Plans**: 4 plans
**Completed**: 2026-07-13 — 4 plans, 4/4 TEST requirements

Plans:
- [x] 04-01-PLAN.md — Schema validation tests for all 15 JSON schemas (TEST-07)
- [x] 04-02-PLAN.md — GitHub Actions CI pipeline + ruff/mypy config (TEST-08)
- [x] 04-03-PLAN.md — Mock-based YouTube Analytics fetcher tests (TEST-09)
- [x] 04-04-PLAN.md — Mock-based Instagram Insights fetcher tests (TEST-10)

### Phase 5: Channel Onboarding & Branding
**Goal**: New YouTube channels can be fully set up through the agent — linked via OAuth, branded with description/tags/avatar/banner/watermark, and pre-configured with default upload settings — so the channel is ready to receive content before the first publish.
**Depends on**: Phase 1 (state management for per-channel config), Phase 2 (secure credential storage for OAuth tokens)
**Requirements**: CHANNEL-01, CHANNEL-02, CHANNEL-03, CHANNEL-04, CHANNEL-05, CHANNEL-06, CHANNEL-07
**Prerequisite manual step**: The user must create their YouTube channel manually via the YouTube/Google interface (linking a Brand Account) — the API cannot create channels, only update existing ones.
**Success Criteria** (what must be TRUE):
   1. User completes OAuth 2.0 flow with offline access; token persists per channel and auto-refreshes before expiry
   2. Channel description, tags/keywords, country, and default language are set via `channels.update` API
   3. Channel profile picture (avatar) uploaded via API
   4. Channel banner image uploaded via API
   5. Branding watermark configured and visible on embedded video player
   6. Default upload settings configured (visibility default, comment moderation defaults, license default, embed toggle)
   7. All channel branding config (avatar path, banner path, description, tags, settings) persisted to `channels/{Name}/channel_config.json`
**Plans**: 3 plans
**Completed**: 2026-07-13 — 3 plans, 7/7 CHANNEL requirements

Plans:
- [x] 05-01-PLAN.md — OAuth token lifecycle + core module refactor (CHANNEL-01)
- [x] 05-02-PLAN.md — Channel branding CLI (description, keywords, banner, watermark) (CHANNEL-02, 03, 04, 05)
- [x] 05-03-PLAN.md — Default upload settings, schema validation, persistence (CHANNEL-06, 07)

### Phase 6: YouTube Publishing
- [x] 05-03-PLAN.md — Default settings & schema validation + persistence (CHANNEL-06, 07)

### Phase 6: YouTube Publishing
**Goal**: Videos are published with complete metadata (category, language, playlist, chapters, audience settings), SEO-optimized title/desc/tags, thumbnail, pin comment, and the ability to update everything post-hoc. Dual-credential partitioning prevents scraper quota from blocking publishes.
**Depends on**: Phase 1 (QuotaBudget, checkpoints, dual-credential state), Phase 2 (secure credential storage for OAuth tokens), Phase 5 (channel must be branded with default settings before publishing)
**Requirements**: PUBLISH-01, PUBLISH-02, PUBLISH-03, PUBLISH-04, PUBLISH-05, PUBLISH-06, PUBLISH-07, PUBLISH-08, PUBLISH-09, PUBLISH-10, PUBLISH-11, PUBLISH-12, PUBLISH-13
**Success Criteria** (what must be TRUE):
   1. User completes OAuth 2.0 flow with offline access; token persists per channel and auto-refreshes before expiry
   2. Upload flow runs on an isolated OAuth API project, preserving the 10,000 daily quota block solely for verified video publishes and analytics retrieval
   3. Scraping uses separate API-key-only credentials (Project A) so quota exhaustion from competitor discovery never blocks publishing
   4. Video uploads succeed via resumable protocol with 256KB-multiple chunks, exponential backoff, and progress reporting; thumbnail upload via `thumbnails.set`
   5. LLM generates on-brand title, description, tags, category, and age rating for each video; user can review generated metadata before posting
   6. Thumbnail is auto-extracted from a video keyframe or accepts user-provided image; uploaded via `thumbnails.set`
   7. Uploads support public/private/unlisted visibility and future-dated `publishAt` scheduling
   8. Publishing configuration (channel ID, privacy defaults, upload settings) reads from per-channel `channel_config.json`
   9. Video assigned to playlist(s) during or after upload via PlaylistItems API
   10. Full metadata set on upload: YouTube category, video language, recording date/location, made-for-kids designation, age restriction, license (standard vs CC), embed enabled/disabled, comments enabled/disabled
   11. Chapter markers auto-generated in the video description from per-scene timestamps (scene_01, scene_02, ...)
   12. A comment is pinned on the published video (e.g., timestamp links, CTA, pinned Q&A prompt)
   13. Video metadata (title, description, tags, thumbnail, playlist assignment) can be updated post-hoc after publish
**Plans**: 3 plans
**Completed**: 2026-07-13 — 3 plans, 13/13 PUBLISH requirements

Plans:
- [x] 06-01-PLAN.md — Resumable upload engine + thumbnail + quota integration (PUBLISH-02, 05, 06, 07)
- [x] 06-02-PLAN.md — SEO metadata generation + chapter markers + full snippet (PUBLISH-04, 10)
- [x] 06-03-PLAN.md — Post-publish actions: playlist, comment, metadata update (PUBLISH-09, 11, 12, 13)

### Phase 7: Analytics Collection & Storage
**Goal**: Performance data from published videos is collected on-demand in a dual-phase workflow — basic velocity metrics at 24h+, deep behavioral metrics at 72h+ — validated against schema, and persisted for downstream analysis.
**Depends on**: Phase 6 (needs published videos to collect analytics)
**Requirements**: ANALYTICS-01, ANALYTICS-02, ANALYTICS-06
**Success Criteria** (what must be TRUE):
    1. Basic public metrics (view count) collected 24+ hours post-publish to assess initial velocity
    2. Deep analytical metrics (CTR, AVD, audience retention) collected after 72+ hours since video's public publish timestamp — YouTube Analytics API requires 48-72h to stabilize retention data
    3. Each video's analytics entry stored as JSONL with schema-validated fields split by tier (basic at 24h, full at 72h)
    4. Aggregate functions in `analytics/insights.py` compile metrics across channels: averages, trends, and comparative rankings
**Plans**: 2 plans (both complete)

Plans:
- [x] 07-01-PLAN.md — Analytics Collector: collect_for_video, collect_recent, persist_entry, thin CLI (ANALYTICS-01, 02)
- [x] 07-02-PLAN.md — Analytics Insights: per-channel stats, cross-channel comparison (ANALYTICS-06)

### Phase 8: Brain Evolution Loop
**Goal**: The agent brain automatically evolves its learning weights from real performance data, closing the content strategy feedback loop.
**Depends on**: Phase 7 (needs analytics data as input for weight updates)
**Requirements**: ANALYTICS-03, ANALYTICS-04, ANALYTICS-05, ANALYTICS-07
**Success Criteria** (what must be TRUE):
   1. Cross-channel insight aggregation detects meaningful patterns across collected data (e.g., "Short-form outperforms long-form on Channel A")
   2. Brain weight updater transforms learning weights by calculating performance ratios from analytics (ICP relevance, timeliness, etc.)
   3. Updated brain weights are integrated into the scoring engine so future topic scores reflect learned performance patterns
   4. Weight updates only trigger after minimum 3 videos per content pillar to prevent overfitting to noise
**Plans**: 2 plans
**Completed**: 2026-07-14 — 2 plans, 4/4 ANALYTICS requirements

Plans:
- [x] 08-01-PLAN.md — Brain updater & batch collection: update_weights, update_hook_preferences, update_performance_patterns, update_brain, run_scheduled_collection (ANALYTICS-03, 04, 07)
- [x] 08-02-PLAN.md — Scoring engine integration: channel-aware brain loading, scoring with updated weights (ANALYTICS-05)

### Phase 9: Audio Production (Per-Scene)
**Goal**: Script converted to per-scene TTS audio with word-level force alignment and per-scene subtitle generation. Scene script files are rewritten inline with timestamps so the ``_script.txt`` is the single canonical timestamp artifact — no separate ``_alignment.json`` needed.
**Depends on**: Phase 1 (scene-level checkpoints for audio artifacts)
**Requirements**: PROD-AUDIO-01, PROD-AUDIO-02, PROD-AUDIO-03, PROD-AUDIO-04, PROD-AUDIO-05, PROD-AUDIO-06
**Parallelizable with**: Phase 10 (Visual Asset Pipeline) — no data dependency between audio and visual
**Success Criteria** (what must be TRUE):
   1. Production pipeline splits script into numbered scenes; each scene gets its own `scene_XX_script.txt`
   2. Per-scene TTS generation: each `scene_XX_script.txt` → `scene_XX_audio.wav` via multi-provider fallback chain (`custom → gemini → google_cloud → edge`)
   3. Per-scene force alignment: each `scene_XX_audio.wav` → word-level timestamps via Groq Whisper API (primary) or local `faster-whisper` (fallback)
   4. After alignment, `scene_XX_script.txt` is rewritten with inline `word[START-END]` annotations — the script file becomes the single canonical timestamp source
   5. Per-scene subtitle files generated from aligned transcript (SRT/VTT format) — burned into the video at render time via HyperFrames
   6. Generated audio marked as temp asset — stored in `channels/{Name}/active_production/`, cleaned up after final video published
   7. Custom TTS CLI (`agent_core/audio/tts/generate.py`) adapted as primary provider via subprocess shell-out; ``TTS_PROXY_URL`` / ``TTS_API_KEY`` env vars override
   8. `faster-whisper` version pinned; alignment accuracy validated against test corpus; ≥90% word accuracy
**Plans**: 3 plans
**Completed**: 2026-07-14 — 3 plans, 6/6 PROD-AUDIO requirements

Plans:
- [x] 09-01-PLAN.md — TTS provider abstraction (Gemini → Google Cloud → Edge fallback) + script splitter + package scaffolding
- [x] 09-02-PLAN.md — Force alignment (Groq API + faster-whisper fallback) + SRT/VTT subtitle generation
- [x] 09-03-PLAN.md — Pipeline orchestrator + temp asset lifecycle + inline timestamp annotation + full test suite (439 tests, 0 failures)

### Phase 10: Visual Asset Pipeline
**Goal**: Stock API sourcing (Pexels/Pixabay/Freesound/Wikimedia Commons), character SVG models, global + per-channel consistent asset library with SQLite-backed cache, and Wikimedia Commons integration with British Library vintage illustration preference.
**Depends on**: Phase 1 (scene-level checkpoints for asset artifacts)
**Requirements**: PROD-VISUAL-01, PROD-VISUAL-02, PROD-VISUAL-03, PROD-VISUAL-04, PROD-VISUAL-05, PROD-VISUAL-06, PROD-VISUAL-07, PROD-VISUAL-08, PROD-VISUAL-09
**Parallelizable with**: Phase 9 (Audio Production) — no data dependency
**Success Criteria** (what must be TRUE):
    1. Asset storage split into consistent (`assets/consistent/global/` + `channels/{Name}/assets/`) and temp (`channels/{Name}/active_production/`)
    2. Character SVG models as first-class consistent assets
    3. Pexels API → B-roll/images; Pixabay fallback; Freesound API → SFX; Wikimedia Commons → public-domain/CC images (no API key)
    4. SQLite-backed asset cache with TTL eviction
    5. All stock API rate limits and quotas respected
    6. Wikimedia Commons integration with British Library preference: first searches BL uploads for vintage/historical illustrations, falls back to generic Commons search
**Plans**: 5 plans
**Completed**: 2026-07-17 — 5 plans, 9/9 PROD-VISUAL requirements

Plans:
- [x] 10-01-PLAN.md — Foundation: BaseAssetProvider ABC, AssetResult, storage helpers, SQLite AssetCache with TTL, search query generation, tests (78 tests)
- [x] 10-02-PLAN.md — Character SVG resolver: CharacterResolver with metadata sidecars, variant lookup, channel override priority, tests
- [x] 10-03-PLAN.md — Stock API providers: PexelsProvider, PixabayProvider, FreesoundProvider, AssetFallbackChain, quota protection, tests
- [x] 10-04-PLAN.md — Public API barrel + dependency cleanup: full agent_core/assets/__init__.py with all 18 symbols, pyproject.toml cleanup
- [x] 10-05-PLAN.md — Wikimedia Commons provider: free public-domain/CC image provider, British Library vintage illustration preference, no API key needed, 27 tests

### Phase 11: Scene Assembly & Final Render
**Goal**: Per-scene two-pass render (HyperFrames GSAP compositions → Playwright → FFmpeg) → assembly with crossfade transitions + subtitle overlay → multi-format output (16:9 / 9:16 / 1:1) → temp cleanup integration.
**Depends on**: Phase 9 (per-scene audio + subtitles), Phase 10 (B-roll, character SVGs, assets)
**Requirements**: PROD-RENDER-01, PROD-RENDER-02, PROD-RENDER-03, PROD-RENDER-04, PROD-RENDER-05, PROD-RENDER-06, PROD-RENDER-07
**Success Criteria** (what must be TRUE):
    1. Production workflow splits script into numbered scenes before generation begins
    2. Two-pass hybrid rendering per scene: Playwright renders per-scene HyperFrames composition (GSAP timeline, data-* attributes) via video recording, FFmpeg converts to MP4 clip
    3. All rendered scene clips assembled into final video with crossfade transitions between scenes
    4. Per-scene subtitle tracks (SRT/VTT from PROD-AUDIO-05) overlaid onto corresponding scene clips
    5. Multi-format output (16:9 long-form, 9:16 Shorts, 1:1 Instagram) from assembled master
    6. Temp assets cleaned up after final video is published
    7. Render config moved into `channel_config.json` per channel
**Plans**: 3 plans
**Completed**: 2026-07-17 — 3 plans, 7/7 PROD-RENDER requirements

Plans:
- [x] 11-01-PLAN.md — Render foundation: agent_core/render/ module, FFmpegUtils, scene rendering (HyperFrames GSAP compositions → Playwright → FFmpeg), RenderPipeline orchestrator, tests
- [x] 11-02-PLAN.md — Assembly + subtitles: crossfade transitions, SRT/VTT subtitle overlay, multi-format output (16:9/9:16/1:1), tests
- [x] 11-03-PLAN.md — Temp lifecycle + render config + integration: render config in channel_config.json, full pipeline integration tests, 77 total render tests

### Phase 12: Recon Efficiency Rework
**Goal**: Eliminate unnecessary video downloads by extracting YouTube captions first (free, instant), using Instagram post captions as transcripts when sufficient, upgrading the transcript cache from flat files to SQLite, and switching the default transcription provider to Groq (free tier).
**Depends on**: Phase 6 (YouTube publishing credentials), Phase 9 (Groq API key for transcription)
**Requirements**: RECON-EFF-01, RECON-EFF-02, RECON-EFF-03, RECON-EFF-04, RECON-EFF-05, RECON-EFF-06, RECON-EFF-07
**Success Criteria** (what must be TRUE):
    1. YouTube competitor analysis does NOT download+transcribe videos that have valid auto-captions — extracted via `yt-dlp --skip-download --write-auto-subs` instead
    2. Transcripts from YouTube captions are cleaned of auto-caption artifacts (`[Music]`, repeated words, etc.)
    3. Instagram post captions ≥ 10 words are used directly as transcripts (skip download+transcribe for those)
    4. Groq Whisper API is the default transcription provider (free tier), with local faster-whisper fallback
    5. Transcript cache upgraded from flat `.txt` files to SQLite-backed with TTL eviction and queryable metadata
    6. Multi-language YouTube caption support respects target language config
     7. All existing recon tests pass with updated mocks; new tests cover caption extraction, cleaning, and cache
**Plans**: 3 plans

Plans:
- [ ] 12-01-PLAN.md — Foundation: transcript cleaning, Groq config defaults, SQLite-backed cache
- [ ] 12-02-PLAN.md — Caption-first extraction: YouTube captions + Instagram caption-as-transcript in pipeline
- [ ] 12-03-PLAN.md — Test suite: cleaning, cache, and config tests

### Phase 13: Agent Documentation
**Goal**: Full pipeline workflow is documented in agent-facing markdown files (AGENTS.md, process-specific guides) so any AI CLI (OpenCode, Claude Code, Codex) can autonomously orchestrate the CreatorForge pipeline from discovery through publishing.
**Depends on**: Phase 12 (recon pipeline must be efficient before documenting)
**Requirements**: DOC-01, DOC-02
**Success Criteria** (what must be TRUE):
    1. `AGENTS.md` (or equivalent for OpenCode) at project root describes the full pipeline workflow: discover → angle → script → produce → publish → analyze → learn
    2. Process-specific markdown files in `.agents/docs/` describe each stage in detail: input contracts, output artifacts, available commands, error recovery procedures
    3. Process-specific docs note YouTube Studio manual-only operations (end screens, cards, thumbnail A/B testing) as human handoff steps
    4. A CLI tool or agent can follow the documentation to autonomously run the full pipeline end-to-end without human intervention
**Plans**: TBD

---

## Dependency Graph

```
Phase 1 (Foundation & Pipeline)
  ├── Phase 2 (Security & Packaging)
  │     └── Phase 3 (Test Framework & Unit Tests)
  │           └── Phase 4 (CI & Extended Tests)
  ├── Phase 5 (Channel Onboarding & Branding) ←─ prerequisite for publishing
  ├── Phase 6 (YouTube Publishing) ←─ needs branded channel
  │     └── Phase 7 (Analytics Collection)
  │           └── Phase 8 (Brain Evolution Loop) ✓
  ├── Phase 9 (Audio Production) ✓ ──┐
  ├── Phase 10 (Visual Pipeline) ✓ ──┤
  │               ┌───────────────────┘
  │               ▼
  ├── Phase 11 (Scene Assembly & Render) ←─ Phase 9 + Phase 10 outputs
  │
  ├── Phase 12 (Recon Efficiency Rework) ←─ needs Groq API key
  │
  └── Phase 13 (Agent Documentation)
```

---

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation & Pipeline Infrastructure | 0/– | Complete ✓ | 2026-07-12 |
| 2. Security Hardening & Packaging | 3/3 | Complete ✓ | 2026-07-12 |
| 3. Test Framework & Core Unit Tests | 6/6 | Complete ✓ | 2026-07-12 |
| 4. CI Pipeline & Extended Tests | 4/4 | Complete ✓ | 2026-07-13 |
| 5. Channel Onboarding & Branding | 3/3 | Complete ✓ | 2026-07-13 |
| 6. YouTube Publishing | 3/3 | Complete ✓ | 2026-07-13 |
| 7. Analytics Collection & Storage | 2/2 | Complete ✓ | 2026-07-13 |
| 8. Brain Evolution Loop | 2/2 | Complete ✓ | 2026-07-14 |
| 9. Audio Production (Per-Scene) | 3/3 | Complete ✓ | 2026-07-14 |
| 10. Visual Asset Pipeline | 5/5 | Complete ✓ | 2026-07-17 |
| 11. Scene Assembly & Final Render | 3/3 | Complete ✓ | 2026-07-17 |
| 12. Recon Efficiency Rework | 0/3 | Planning | — |
| 13. Agent Documentation | 0/– | Not started | - |

---

## Requirement Coverage

| Category | Total | Phase | Mapped | Status |
|----------|-------|-------|--------|--------|
| PIPE (Pipeline Infrastructure) | 7 | Phase 1 | 7/7 ✓ | Complete |
| SEC (Security & Packaging) | 8 | Phase 2 | 8/8 ✓ | Complete |
| TEST (Test Infrastructure) | 10 | Phases 3-4 | 10/10 ✓ | Complete |
| CHANNEL (Channel Onboarding & Branding) | 7 | Phase 5 | 7/7 ✓ | Complete |
| PUBLISH (YouTube Publishing) | 13 | Phase 6 | 13/13 ✓ | Complete |
| ANALYTICS (Analytics & Brain) | 7 | Phases 7-8 | 7/7 ✓ | Complete |
| PROD-AUDIO (Audio Production) | 6 | Phase 9 | 6/6 ✓ | Complete |
| PROD-VISUAL (Visual Assets) | 9 | Phase 10 | 9/9 ✓ | Complete (+ Wikimedia Commons provider) |
| PROD-RENDER (Scene Assembly & Render) | 7 | Phase 11 | 7/7 ✓ | Complete ✓ |
| RECON-EFF (Recon Efficiency) | 7 | Phase 12 | 7/7 ✓ | Planning |
| DOC (Agent Documentation) | 2 | Phase 13 | 2/2 ✓ | Pending |
| **Total** | **83** | **13 phases** | **83/83 ✓** | **11/13 complete** |

---

*Created: 2026-07-10*
*Granularity: fine*
*Revised: 2026-07-18 — Phase 12 redefined as Recon Efficiency Rework; Phase 13 = Agent Documentation; ROADMAP.md updated*
