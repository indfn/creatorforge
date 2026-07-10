# CreatorForge Roadmap

**Core Value:** One command from idea to published video: discover competitor patterns → generate script → produce video → publish → learn from results.

---

## Phases

- [ ] **Phase 1: Foundation & Pipeline Infrastructure** — Build checkpoint system, quality gates, QuotaBudget service, and state management that every other phase depends on
- [ ] **Phase 2: Security Hardening & Packaging** — Fix all known security vulnerabilities and properly package the project as a pip-installable module
- [ ] **Phase 3: Test Framework & Core Unit Tests** — Set up pytest and write comprehensive unit tests for existing core logic modules
- [ ] **Phase 4: CI Pipeline & Extended Tests** — Add schema validation tests, mock-based API tests, and GitHub Actions automation
- [ ] **Phase 5: YouTube Publishing** — Implement OAuth 2.0 with dual-credential partitioning, resumable upload with thumbnails, SEO metadata generation, and publication scheduling
- [ ] **Phase 6: Analytics Collection & Storage** — Dual-phase polling (24h basic + 72h deep), schema-validated persistence
- [ ] **Phase 7: Brain Evolution Loop** — Evolve agent brain learning weights from real performance data to close the content strategy feedback loop
- [ ] **Phase 8: Audio Production** — Implement multi-provider TTS fallback chain and word-level force alignment for captions
- [ ] **Phase 9: Visual Asset Pipeline** — Source B-roll footage, images, and sound effects from stock APIs with local caching
- [ ] **Phase 10: Video Rendering (Two-Pass Hybrid)** — HyperFrames Puppeteer rasterization → FFmpeg composition with multi-format output
- [ ] **Phase 11: Agent Documentation** — Write AGENTS.md workflow directives and process-specific markdown files for agentic automation

---

## Phase Details

### Phase 1: Foundation & Pipeline Infrastructure
**Goal**: Pipeline stages can produce typed, schema-validated checkpoint artifacts, resume from crashes, share the QuotaBudget service safely, and support dual-credential partitioning (scraping vs publishing).
**Depends on**: Nothing
**Requirements**: PIPE-01, PIPE-02, PIPE-03, PIPE-04, PIPE-05, PIPE-06
**Non-requirement action**: Kick off Google OAuth consent screen audit and YouTube API quota extension request (2-4 week lead time — must start immediately to avoid blocking Phase 5)
**Success Criteria** (what must be TRUE):
  1. Every pipeline stage produces a typed JSON artifact validated against its JSON Schema contract
  2. Pipeline can resume from the last successful checkpoint after a crash or restart without re-running completed stages
  3. QuotaBudget shared service tracks daily quota consumption per API and rejects requests when budget is exhausted
  4. State management supports separate credential loading for scraping projects (API Key) and channel publishing projects (OAuth 2.0)
  5. State files use file locking via `portalocker` to prevent concurrent access corruption
  6. In-memory `active_jobs` dict uses LRU eviction with a configurable maximum capacity
**Plans**: TBD

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
**Plans**: TBD

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
**Plans**: TBD

### Phase 4: CI Pipeline & Extended Tests
**Goal**: Schema validation tests, external API mock tests, and automated CI pipeline ensure code quality gates are enforced on every change.
**Depends on**: Phase 3
**Requirements**: TEST-07, TEST-08, TEST-09, TEST-10
**Success Criteria** (what must be TRUE):
  1. All 12 JSON Schema files have validation tests: valid fixtures pass, known-invalid fixtures are properly rejected
  2. GitHub Actions CI pipeline runs ruff lint, mypy type-check, and pytest on every push and pull request
  3. YouTube Analytics fetcher uses mocks to verify API response parsing, quota handling, and error recovery
  4. Instagram Insights fetcher uses mocks to verify API response parsing, token refresh, and error recovery
**Plans**: TBD

### Phase 5: YouTube Publishing
**Goal**: Users can authorize their YouTube channel via OAuth, upload videos with SEO-optimized metadata and thumbnails, control privacy, schedule publication, and operate within API quota limits using dual-credential partitioning.
**Depends on**: Phase 1 (QuotaBudget, checkpoints, dual-credential state), Phase 2 (secure credential storage for OAuth tokens)
**Requirements**: PUBLISH-01, PUBLISH-02, PUBLISH-03, PUBLISH-04, PUBLISH-05, PUBLISH-06, PUBLISH-07
**Success Criteria** (what must be TRUE):
  1. User completes OAuth 2.0 flow with offline access; token persists per channel and auto-refreshes before expiry
  2. The upload flow runs on an isolated OAuth API project, preserving the 10,000 daily quota block solely for verified video publishes and analytics retrieval
  3. Scraping uses separate API-key-only credentials (Project A) so quota exhaustion from competitor discovery never blocks publishing
  4. Video uploads succeed via resumable protocol with 256KB-multiple chunks, exponential backoff, and progress reporting; thumbnail upload via `thumbnails.set`
  5. LLM generates on-brand title, description, tags, category, and age rating for each video; user can review generated metadata before posting
  6. Thumbnail is auto-extracted from a video keyframe or accepts user-provided image; uploaded via `thumbnails.set`
  7. Uploads support public/private/unlisted visibility and future-dated `publishAt` scheduling
  8. Publishing configuration (channel ID, privacy defaults, upload settings) reads from per-channel `channel_config.json`
**Plans**: TBD

### Phase 6: Analytics Collection & Storage
**Goal**: Performance data from published videos is collected in a dual-phase polling loop — basic velocity metrics at 24h, deep behavioral metrics at 72h — validated against schema, and persisted for downstream analysis.
**Depends on**: Phase 5 (needs published videos to collect analytics)
**Requirements**: ANALYTICS-01, ANALYTICS-02, ANALYTICS-06
**Success Criteria** (what must be TRUE):
  1. Basic public metrics (view count) polled 24 hours post-publish to assess initial velocity
  2. Deep analytical metrics (CTR, AVD, audience retention) exclusively polled after a mandatory 72-hour delay since video's public publish timestamp — YouTube Analytics API requires 48-72h to stabilize retention data
  3. Each video's analytics entry stored as JSONL with schema-validated fields split by tier (basic at 24h, full at 72h)
  4. Aggregate functions in `analytics/insights.py` compile metrics across channels: averages, trends, and comparative rankings
**Plans**: TBD

### Phase 7: Brain Evolution Loop
**Goal**: The agent brain automatically evolves its learning weights from real performance data, closing the content strategy feedback loop.
**Depends on**: Phase 6 (needs analytics data as input for weight updates)
**Requirements**: ANALYTICS-03, ANALYTICS-04, ANALYTICS-05, ANALYTICS-07
**Success Criteria** (what must be TRUE):
  1. Cross-channel insight aggregation detects meaningful patterns across collected data (e.g., "Short-form outperforms long-form on Channel A")
  2. Brain weight updater transforms learning weights by calculating performance ratios from analytics (ICP relevance, timeliness, etc.)
  3. Updated brain weights are integrated into the scoring engine so future topic scores reflect learned performance patterns
  4. Weight updates only trigger after minimum 3 videos per content pillar to prevent overfitting to noise
**Plans**: TBD

### Phase 8: Audio Production
**Goal**: Scripts can be converted to speech with automatic fallback between TTS providers and word-level caption timing via force alignment.
**Depends on**: Phase 1 (checkpoints for audio artifacts between pipeline stages)
**Requirements**: PROD-AUDIO-01, PROD-AUDIO-02, PROD-AUDIO-03, PROD-AUDIO-04
**Parallelizable with**: Phase 9 (Visual Asset Pipeline) — no data dependency between audio and visual
**Success Criteria** (what must be TRUE):
  1. TTS provider selector tries Gemini first, falls back to Google Cloud TTS then Edge TTS; a single provider failure doesn't abort the pipeline
  2. Word-level force alignment via `faster-whisper` produces accurate timestamps for 90%+ of words in testing
  3. `faster-whisper` version is pinned in dependencies; alignment accuracy is validated against a test corpus
  4. Aligned transcript outputs integrate with scene timing data for caption overlay rendering
**Plans**: TBD

### Phase 9: Visual Asset Pipeline
**Goal**: B-roll footage, images, and sound effects are automatically sourced from stock media APIs with local caching and graceful degradation on rate limits.
**Depends on**: Phase 1 (checkpoints for asset artifacts between pipeline stages)
**Requirements**: PROD-VISUAL-01, PROD-VISUAL-02, PROD-VISUAL-03, PROD-VISUAL-04, PROD-VISUAL-05, PROD-VISUAL-06
**Parallelizable with**: Phase 8 (Audio Production) — no data dependency between visual and audio
**Success Criteria** (what must be TRUE):
  1. Pexels API returns relevant B-roll footage and images from keyword search; results cached locally with configurable TTL
  2. Pixabay API serves as fallback when Pexels has no results, hits rate limits, or returns errors
  3. Freesound API returns relevant sound effects from content-based search terms with configurable filters
  4. Asset cache is SQLite-backed with TTL-based eviction; cache hits serve instantly without API calls
  5. All stock API rate limits and quotas are respected; clear error messages when limits are hit with retry hints
  6. Unused commented-out Pillow/matplotlib dependencies are removed or moved to optional extras groups
**Plans**: TBD

### Phase 10: Video Rendering (Two-Pass Hybrid)
**Goal**: Complete videos are rendered via a two-pass hybrid chain — HyperFrames Puppeteer rasterization of DOM/SVG animations piped into FFmpeg for final composition with multi-format output.
**Depends on**: Phase 1 (checkpoints for render artifacts), Phase 8 (aligned audio output), Phase 9 (visual assets output)
**Requirements**: PROD-RENDER-01, PROD-RENDER-02, PROD-RENDER-03, PROD-RENDER-04, PROD-RENDER-05
**Success Criteria** (what must be TRUE):
  1. **Pass 1 — Visual Rasterization**: HyperFrames runs Puppeteer inside a headless shell to rasterize DOM/SVG character animations and CSS keyframes frame-by-frame, piping raw frames into FFmpeg
  2. **Pass 2 — FFmpeg Composition**: FFmpeg accepts the incoming visual frame stream, overlays the synced TTS audio track, and packages into target format container
  3. Render supports 16:9 long-form, 9:16 Shorts, and 1:1 Instagram output formats from the same source assets
  4. Final video includes TTS audio track, time-synced word-level captions, HyperFrames scene animations (stickman explainers, dynamic charts), and visual assets (B-roll, images, SFX)
  5. Scene template renderer supports text overlays, transitions between scenes, and configurable visual styling via HyperFrames HTML/CSS blueprints
  6. Render configuration (resolution, format, templates, quality presets) reads from per-channel `channel_config.json`
**Plans**: TBD

### Phase 11: Agent Documentation
**Goal**: Full pipeline workflow is documented in agent-facing markdown files (AGENTS.md, process-specific guides) so any AI CLI (OpenCode, Claude Code, Codex) can autonomously orchestrate the CreatorForge pipeline from discovery through publishing.
**Depends on**: Phase 10 (need complete pipeline before documenting it)
**Requirements**: DOC-01, DOC-02
**Success Criteria** (what must be TRUE):
  1. `AGENTS.md` (or equivalent for OpenCode) at project root describes the full pipeline workflow: discover → angle → script → produce → publish → analyze → learn
  2. Process-specific markdown files in `.agents/docs/` describe each stage in detail: input contracts, output artifacts, available commands, error recovery procedures
  3. A CLI tool or agent can follow the documentation to autonomously run the full pipeline end-to-end without human intervention
**Plans**: TBD

---

## Dependency Graph

```
Phase 1 (Foundation & Pipeline)
  ├── Phase 2 (Security & Packaging)
  │     └── Phase 3 (Test Framework & Unit Tests)
  │           └── Phase 4 (CI & Extended Tests)
  ├── Phase 5 (YouTube Publishing)
  │     └── Phase 6 (Analytics Collection)
  │           └── Phase 7 (Brain Evolution Loop)
  ├── Phase 8 (Audio Production) ──┐
  ├── Phase 9 (Visual Pipeline) ───┤
  │                                │
  ├── Phase 10 (Video Rendering) ←─┘
  │
  └── Phase 11 (Agent Documentation)
```

---

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation & Pipeline Infrastructure | 0/– | Not started | - |
| 2. Security Hardening & Packaging | 0/– | Not started | - |
| 3. Test Framework & Core Unit Tests | 0/– | Not started | - |
| 4. CI Pipeline & Extended Tests | 0/– | Not started | - |
| 5. YouTube Publishing | 0/– | Not started | - |
| 6. Analytics Collection & Storage | 0/– | Not started | - |
| 7. Brain Evolution Loop | 0/– | Not started | - |
| 8. Audio Production | 0/– | Not started | - |
| 9. Visual Asset Pipeline | 0/– | Not started | - |
| 10. Video Rendering (Two-Pass Hybrid) | 0/– | Not started | - |
| 11. Agent Documentation | 0/– | Not started | - |

---

## Requirement Coverage

| Category | Total | Phase | Mapped |
|----------|-------|-------|--------|
| PIPE (Pipeline Infrastructure) | 6 | Phase 1 | 6/6 ✓ |
| SEC (Security & Packaging) | 8 | Phase 2 | 8/8 ✓ |
| TEST (Test Infrastructure) | 10 | Phases 3-4 | 10/10 ✓ |
| PUBLISH (YouTube Publishing) | 8 | Phase 5 | 8/8 ✓ |
| ANALYTICS (Analytics & Brain) | 7 | Phases 6-7 | 7/7 ✓ |
| PROD-AUDIO (Audio Production) | 4 | Phase 8 | 4/4 ✓ |
| PROD-VISUAL (Visual Assets) | 6 | Phase 9 | 6/6 ✓ |
| PROD-RENDER (Video Rendering) | 5 | Phase 10 | 5/5 ✓ |
| DOC (Agent Documentation) | 2 | Phase 11 | 2/2 ✓ |
| **Total** | **56** | **11 phases** | **56/56 ✓** |

---

*Created: 2026-07-10*
*Granularity: fine*
*Revised: 2026-07-10 — added dual-credential partitioning (Phase 5), 72h analytics polling (Phase 6), Puppeteer two-pass rendering (Phase 10), Agent Documentation (Phase 11)*
