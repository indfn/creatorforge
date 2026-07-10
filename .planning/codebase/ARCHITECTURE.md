# Architecture

**Analysis Date:** 2026-07-10

## Pattern Overview

**Overall:** Modular pipeline architecture with agent brain feedback loop

The system is structured around a 5-stage content lifecycle: **Discover → Angle → Script → Post → Analyze**, with each stage feeding into the next and the final stage updating the central "agent brain" that influences future discovery.

**Key Characteristics:**
- **Pipeline-oriented**: Each stage (recon, scoring, production, publishing, analytics) is a self-contained module with clear input/output contracts
- **Agent-brain centric**: A central `agent-brain.json` file stores ICP (Ideal Customer Profile), pillars, learning weights, and competitor config — all modules read from and write to this file
- **JSON-schema validated**: All inter-module data is validated against JSON Schema draft-07 contracts in `schemas/`
- **Ported from ReelRecon**: Core recon and skeleton ripper modules were ported from an external project (`ReelRecon`) with imports and paths adjusted
- **Dual-interface**: Commands available both as AI CLI commands (`/viral:*`) in `.agents/commands/` and as programmatic Python modules in `agent_core/`
- **Multi-channel**: Supports multiple YouTube channels via `channels/{Name}/` directories with independent configs and brains

## Layers

**Discovery Layer (Recon):**
- Purpose: Competitor content scraping, transcription, pattern extraction, and topic generation
- Location: `agent_core/recon/`
- Contains: Instagram/YouTube scrapers, video downloader, transcript cache, LLM-based skeleton extractor, pattern aggregator/synthesizer, bridge to topic pipeline
- Depends on: `agent_core/scoring/` (engine), `agent_core/recon/config` (credentials)
- Used by: Recon Flask UI (`agent_core/recon/web/app.py`), skeleton ripper pipeline, bridge module

**Scoring Layer:**
- Purpose: Score topics against agent brain ICP keywords, pillars, and learning weights
- Location: `agent_core/scoring/`
- Contains: `engine.py` (4-criteria scoring: icp_relevance, timeliness, content_gap, proof_potential), `rescore.py` (bulk rescore utility)
- Depends on: `agent_core/data/agent-brain.json` (read-only)
- Used by: Recon bridge (`agent_core/recon/bridge.py`), rescore CLI, `agent_core/scoring/__init__.py` exports

**Analytics Layer:**
- Purpose: Performance data collection, cross-channel insight aggregation, brain evolution
- Location: `agent_core/analytics/`
- Contains: `collector.py` (YouTube Analytics API stub), `insights.py` (cross-channel aggregation stub), `brain_updater.py` (learning weight evolution stub)
- Depends on: `agent_core/data/` (analytics entries, brain.json)
- Used by: AI commands (`/viral:analyze`, `/viral:update-brain`)

**Publishing Layer:**
- Purpose: YouTube upload, OAuth management, scheduling, metadata optimization
- Location: `agent_core/publishing/`
- Contains: `uploader.py` (YouTube Data API v3 upload CLI), `oauth.py` (Google OAuth handler stub), `scheduler.py` (peak-time calculator stub), `metadata.py` (SEO metadata generator stub)
- Depends on: `channels/{name}/channel_config.json` (per-channel YouTube config)
- Used by: AI command (`/viral:post`)

**Production Layer:**
- Purpose: Audio generation, visual/scene rendering, pre-render validation
- Location: `production/`
- Contains: `AudioGeneration/` (TTS via Gemini 3.1 Flash, force alignment stub), `RenderEngine/` (linting, HTML templates), `VisualGeneration/` (asset scraping, SFX scraping, fallback chart generation stubs)
- Depends on: `channels/{name}/active_production/` (working directory), external APIs (Gemini TTS, Pexels, Pixabay)
- Used by: AI commands (`/viral:produce`, `/viral:render`)

**Configuration Layer:**
- Purpose: Environment loading, credential management, competitor config
- Location: `agent_core/recon/config.py`
- Contains: `ReconConfig` dataclass, `Competitor` dataclass, credential loading (`.env` → `.credentials` → env vars cascade), competitor loading from `agent-brain.json`
- Used by: All recon modules, Flask UI

## Data Flow

**Competitor Discovery Flow:**

1. User triggers `/viral:discover` or clicks "Scrape" in Recon UI
2. `InstaClient` (Instagram) or `get_channel_videos` (YouTube) scrapes competitor content
3. Video files downloaded to `data/recon/temp/` and transcribed via OpenAI Whisper API (or local Whisper)
4. Transcripts cached in `data/recon/cache/`; `TranscriptCache` prevents redundant API calls
5. `SkeletonRipperPipeline` orchestrates: scrape → transcribe → extract (LLM-based skeleton parsing) → aggregate → synthesize
6. Extracted skeletons stored in `data/recon/reports/{timestamp}_{jobid}/skeletons.json`
7. `bridge.py` converts skeletons into scored topics via `scoring/engine.py`
8. Topics saved as JSONL to `data/topics/{date}-topics.jsonl`
9. `tracker.py` persists seen-content state to `data/recon/tracker-state.json` to prevent duplicate processing

**Production Flow:**

1. Script data flows to `production/AudioGeneration/tts_generation.py` for TTS generation
2. Audio goes to `production/AudioGeneration/force_align.py` for word-level timestamp alignment
3. `production/RenderEngine/linter.py` validates the production workspace
4. Visual assets fetched via `production/VisualGeneration/` scrapers
5. Final render uses `production/RenderEngine/` templates for assembly

**Brain Feedback Loop:**

1. Analytics collected via `analytics/collector.py`
2. Patterns aggregated via `analytics/insights.py`
3. Learning weights updated via `analytics/brain_updater.py`
4. Updated `agent-brain.json` influences future `scoring/engine.py` scores

**State Management:**
- **Persistent Brain**: `data/agent-brain.json` — the central state file containing ICP, pillars, competitors, learning weights
- **Per-channel Config**: `channels/{name}/channel_config.json` — YouTube credentials, TTS voice config, render settings
- **Per-channel Brain**: `channels/{name}/brain.json` — channel-specific brain state
- **Tracker State**: `data/recon/tracker-state.json` — deduplication state for competitor content processing
- **Transcript Cache**: `data/recon/cache/` — filesystem cache of transcribed competitor videos
- **SQLite DB**: `data/recon/recon.db` — asset and collection management with FTS5 full-text search
- **Topics Store**: `data/topics/{date}-topics.jsonl` — daily JSONL files of scored topic entries

## Key Abstractions

**Agent Brain:**
- Purpose: Central knowledge store defining the creator's ICP, content pillars, competitors, and learning weights
- File: `data/agent-brain.json`
- Pattern: JSON document consumed read-only by scoring engine, read/write by brain updater

**Skeleton Ripper Pipeline:**
- Purpose: Multi-stage pipeline for competitor content analysis: scrape → transcribe → extract → aggregate → synthesize
- File: `agent_core/recon/skeleton_ripper/pipeline.py`
- Pattern: Stateful pipeline `SkeletonRipperPipeline` with progress callback and dataclass-based job configuration (`JobConfig`, `JobProgress`, `JobResult`)
- Stages: 5 explicit stages tracked by `JobStatus` enum with dataclass progress tracking

**LLM Client:**
- Purpose: Multi-provider abstraction for LLM calls (OpenAI-compatible, Ollama local)
- File: `agent_core/recon/skeleton_ripper/llm_client.py`
- Pattern: Provider registry with `ProviderConfig` dataclasses, retry logic with exponential backoff, configurable via env vars

**Scoring Engine:**
- Purpose: Stateless function collection that scores topic text against brain context
- File: `agent_core/scoring/engine.py`
- Pattern: Pure functions with no side effects (read-only on brain file), 4 criteria with weighted total

**Recon Config:**
- Purpose: Cascading configuration loader with `.env` → `.credentials` → env vars priority
- File: `agent_core/recon/config.py`
- Pattern: Dataclass-based configuration with static factory methods, credential masking

**ReconLogger:**
- Purpose: Singleton thread-safe logger with file rotation, error codes, and structured JSON logging
- File: `agent_core/recon/utils/logger.py`
- Pattern: Singleton with thread-safe initialization, JSON log entries, error code generation

**Asset/Collection Model:**
- Purpose: SQLite-backed CRUD for saved assets with full-text search
- File: `agent_core/recon/storage/models.py`
- Pattern: Dataclass-derived ORM with class methods for CRUD, FTS5 integration

**Production Models:**
- Purpose: Validate production workspace readiness before render
- File: `production/RenderEngine/linter.py`
- Pattern: File existence/validity checks returning structured issue lists with severity levels

## Entry Points

**Recon UI (Flask Web App):**
- Location: `agent_core/recon/web/app.py`
- Triggers: `python3 -m agent_core.recon.web.app` or `bash scripts/run-recon-ui.sh`
- Responsibilities: Competitor management, skeleton analysis, push-to-discover bridge, credential settings
- Port: 5001, host: 0.0.0.0
- Routes: `/` (dashboard), `/skeleton-ripper` (analysis page), `/settings` (credentials)
- API routes: `/api/competitors`, `/api/competitors/*/scrape`, `/api/recon/analyze`, `/api/recon/push-to-discover`, `/api/settings`

**Python Module Entry Points:**
- `agent_core/scoring/rescore.py` — CLI for rescoring existing topics (`python3 scoring/rescore.py [file]`)
- `agent_core/publishing/uploader.py` — CLI for YouTube upload (`python3 -m agent_core.publishing.uploader --channel ChannelA`)
- `agent_core/recon/skeleton_ripper/pipeline.py` — `run_skeleton_ripper()` function as programmatic entry
- `agent_core/recon/bridge.py` — `generate_topics_from_skeletons()` as integration point

**Scripts Entry Points:**
- `scripts/fetch-yt-analytics.py` — YouTube Analytics data fetcher
- `scripts/fetch-ig-insights.py` — Instagram Insights data fetcher
- `scripts/setup-yt-oauth.py` — YouTube OAuth setup
- `scripts/setup-ig-token.py` — Instagram token setup
- `scripts/refresh-ig-token.sh` — Instagram token refresh
- `scripts/generate-pdf.py` — PDF lead magnet generator
- `scripts/run-recon-ui.sh` — Launch Recon Flask UI
- `scripts/init-creatorforge.sh` — Full bootstrap script

**AI CLI Commands:**
- Location: `.agents/commands/`
- `/viral:setup` — Platform connection wizard
- `/viral:onboard` — Agent brain setup
- `/viral:discover` — Topic discovery
- `/viral:angle` — Angle development
- `/viral:script` — Script generation
- `/viral:analyze` — Performance analytics
- `/viral:update-brain` — Brain evolution

## Error Handling

**Strategy:** Defensive with structured logging and error codes

**Patterns:**
- `ReconLogger` generates unique error codes (`CATEGORY-12345-ABCD`) for each error occurrence with full context capture
- LLM calls use retry with exponential backoff (max 3 retries, retryable status codes 429/5xx)
- Skeleton pipeline uses `JobProgress.errors` list to accumulate non-fatal errors while continuing
- Translation layer wraps all API responses in JSON with consistent structure (`{error: "..."}` or `{success: true, ...}`)
- Database operations use `db_transaction()` context manager with automatic rollback on exception
- Null-safety: Many access patterns use `.get("key", default)` to handle missing keys gracefully

## Cross-Cutting Concerns

**Logging:** Structured JSON logging via `ReconLogger` singleton — logs to both console (colored) and rotated files at `data/recon/logs/`. Error codes enable traceability across sessions.

**Validation:** JSON Schema draft-07 schemas in `schemas/` define contracts for topics, analytics, hooks, scripts, and production orders. Not programmatically enforced at runtime — used as references.

**Authentication:** Instagram credentials via Instaloader login with session persistence. YouTube via Google OAuth (tokens stored per-channel). LLM API keys via environment variables.

**Configuration cascading:** OS env vars → `.env` file → `.credentials` file — each level overrides the previous.

---

*Architecture analysis: 2026-07-10*
