# Architecture

**Analysis Date:** 2026-07-09

## Pattern Overview

**Overall:** Modular monolith — a single repository with clearly separated, independently invocable modules. The system is a "trainable social media coaching system for Claude Code" that discovers content topics, develops angles, generates scripts, and learns from performance data through a feedback loop.

**Key Characteristics:**
- **Claude Code command-driven**: 7 `/viral:*` Markdown commands (in `.claude/commands/`) orchestrate the pipeline. Each command is a structured prompt that Claude interprets and executes against the codebase.
- **JSONL+JSON data pipeline**: Data flows through flat JSONL files (`topics/`, `angles/`, `hooks/`, `scripts/`) with a central `data/agent-brain.json` acting as the evolving system memory.
- **Competitor intelligence via `recon/`**: Ported from ReelRecon, this is the scraper/transcriber/analyzer subsystem — the most complex module.
- **JSON Schema contracts**: `schemas/` define the data shapes for every entity in the system.
- **Flat script utilities**: Shell and Python scripts serve as CLI entry points for analytics fetching, PDF generation, and init/setup.

## Component Diagram (text-based)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CLAUDE CODE CLI                              │
│  .claude/commands/viral-{setup,onboard,discover,angle,script,      │
│                          analyze,update-brain}.md                   │
└──────────┬──────────────────────────────────┬──────────────────────┘
           │ interprets & orchestrates         │ triggers
           ▼                                   ▼
┌──────────────────────────┐     ┌──────────────────────────────┐
│      recon/ (Recon)      │     │    scripts/ (Utilities)      │
│                          │     │                              │
│  scraper/                │     │  fetch-ig-insights.py        │
│  ├── instagram.py        │     │  fetch-yt-analytics.py       │
│  ├── youtube.py          │     │  generate-pdf.py             │
│  └── downloader.py       │     │  init-viral-command.sh       │
│                          │     │  run-recon-ui.sh             │
│  skeleton_ripper/        │     │  setup-ig-token.py           │
│  ├── pipeline.py         │     │  setup-yt-oauth.py           │
│  ├── extractor.py        │     │  refresh-ig-token.sh         │
│  ├── aggregator.py       │     └──────────────────────────────┘
│  ├── synthesizer.py      │
│  ├── llm_client.py       │     ┌──────────────────────────────┐
│  ├── cache.py            │     │      scoring/                │
│  └── prompts.py          │     │                              │
│                          │     │  engine.py                   │
│  storage/                │     │  rescore.py                  │
│  ├── database.py         │     └──────────┬───────────────────┘
│  └── models.py           │                │
│                          │                ▼
│  utils/                  │     ┌──────────────────────────────┐
│  ├── logger.py           │     │      data/                   │
│  ├── retry.py            │     │                              │
│  └── state_manager.py    │     │  agent-brain.json            │
│                          │     │  topics/*.jsonl              │
│  web/                    │     │  angles.jsonl                │
│  ├── app.py (Flask)      │     │  hooks.jsonl                │
│  ├── templates/*.html    │     │  scripts.jsonl              │
│  └── static/             │     │  cta-templates.json         │
│                          │     │  analytics/raw/              │
│  config.py               │     │  hooks/                      │
│  bridge.py               │     │  insights/                   │
│  tracker.py              │     └──────────────────────────────┘
└──────────────────────────┘
```

## Key Modules / Components

### `recon/` — Competitor Intelligence (2,620 lines)
- **Purpose**: Scrape competitor content (Instagram & YouTube), transcribe videos, extract content skeletons (hook/value/CTA), aggregate patterns, and synthesize actionable templates.
- **Entry points**: `recon/web/app.py` (Flask UI, port 5001), `recon/bridge.py` (programmatic from Claude commands)
- **Key sub-modules**:
  - `scraper/` — Instagram via `instaloader` (`instagram.py`, 242 lines), YouTube via `yt-dlp` (`youtube.py`, 194 lines), video download + transcription (`downloader.py`, 224 lines, OpenAI Whisper API or local Whisper)
  - `skeleton_ripper/` — Pipeline orchestration (`pipeline.py`, 431 lines), LLM-based extraction (`extractor.py`, 142 lines), aggregation (`aggregator.py`, 117 lines), synthesis (`synthesizer.py`, 130 lines), multi-provider LLM client (`llm_client.py`, 203 lines, supports OpenAI/Anthropic/Google/Ollama), prompt templates (`prompts.py`, 202 lines), transcript caching (`cache.py`, 98 lines)
  - `storage/` — SQLite asset management (`database.py`, 104 lines), CRUD models (`models.py`, 195 lines)
  - `utils/` — Singleton logger with file rotation (`logger.py`, 197 lines), retry with exponential backoff (`retry.py`, 109 lines), job state manager (`state_manager.py`, 57 lines)
  - `web/` — Flask UI dashboard (`app.py`, 382 lines), 3 Jinja2 templates (`competitors.html`, `skeleton_ripper.html`, `settings.html`), tactical CSS (`tactical.css`), minimal JS (`app.js`)
  - `config.py` — Reads competitors from `agent-brain.json`, manages credentials from `.env` or `.credentials` file (129 lines)
  - `bridge.py` — Converts skeletons → scored topics matching `topic.schema.json`, imports `scoring.engine` (244 lines)
  - `tracker.py` — Deduplication state manager, tracks which content has been processed (141 lines)

### `scoring/` — Topic Scoring Engine (450 lines)
- **Purpose**: Score topics against the agent brain's ICP keywords, content pillars, and learning weights. Pure computation, no external dependencies beyond stdlib.
- **Dependencies**: Read-only on `data/agent-brain.json`. Does NOT import from `recon/`.
- `engine.py` (292 lines): 4-criteria scorer — `icp_relevance`, `timeliness`, `content_gap`, `proof_potential` — with competitor validation bonuses and weighted total calculation
- `rescore.py` (132 lines): CLI script to re-score all topics when learning weights change

### `schemas/` — JSON Schema Contracts (10 files)
- Defines schemas for: `agent-brain`, `topic`, `angle`, `hook`, `swipe-hook`, `script`, `insight`, `analytics-entry`, `competitor-reel`
- All draft-07, with enforced `additionalProperties: false`

### `scripts/` — Entry Points & Automation (8 scripts)
- `init-viral-command.sh` (303 lines): Bootstrap — creates directories, init data files, installs deps, symlinks Claude commands
- `run-recon-ui.sh` (39 lines): Launches Flask Recon UI on port 5001
- `generate-pdf.py` (309 lines): PDF lead magnet generation from scripts using ReportLab
- `fetch-yt-analytics.py` (296 lines): YouTube CTR, watch time, subscribers via Data API + Analytics API
- `fetch-ig-insights.py` (285 lines): Instagram Graph API insights (views, reach, saves, follower growth)
- `setup-ig-token.py` / `setup-yt-oauth.py`: OAuth setup for analytics
- `refresh-ig-token.sh`: Token refresh utility
- `init-data.sh`: Data initialization

### `skills/last30days/` — Bundled Discovery Skill
- External skill for researching topics across Reddit, X, YouTube, and web
- Own test suite (`tests/`), fixtures (`fixtures/`), agent config (`agents/openai.yaml`)
- Library at `scripts/lib/` with 20+ modules for search, enrichment, scoring

### `data/` — Data Storage
- `agent-brain.json`: Central evolving system memory (identity, ICP, pillars, competitors, learning weights, performance)
- `topics/*.jsonl`: Discovered topics with scores
- `hooks.jsonl`, `angles.jsonl`, `scripts.jsonl`: Pipeline output JSONL files
- `cta-templates.json`: Platform-specific CTA templates (5 platforms, 6 CTA types each)
- `analytics/raw/`: Raw analytics data
- `recon/competitors/`: Per-competitor scraped data (`reels.json`/`videos.json`)
- `recon/reports/`: Skeleton ripper analysis reports
- `recon/cache/`: Cached transcripts

### `assets/` — Brand Assets
- `gvb-logo.svg`, `install-preview.svg`

## Data Flow

**Discovery Pipeline (competitor → topic → angle → script → PDF):**

1. **Scrape**: Claude command `/viral:discover` triggers `recon/bridge.py` → `recon/skeleton_ripper/pipeline.py` → Instagram via `instaloader` or YouTube via `yt-dlp`
2. **Transcribe**: Video files downloaded to temp dir, transcribed via OpenAI Whisper API (or local Whisper), cached to `data/recon/cache/`
3. **Extract**: `BatchedExtractor` sends transcripts to LLM (OpenAI/Anthropic/Google/Ollama), extracts structured skeletons (hook, value, CTA)
4. **Aggregate**: `SkeletonAggregator` produces stats (avg hook length, technique distribution, view stats)
5. **Synthesize**: `PatternSynthesizer` calls LLM for fill-in-the-blank templates
6. **Bridge**: `bridge.py` converts skeletons → topics → `scoring.engine.score_topic()` → saves to `data/topics/*.jsonl`
7. **Angle → Script → Analyze**: Subsequent `/viral:angle`, `/viral:script`, `/viral:analyze` commands consume the topics pipeline
8. **Feedback Loop**: `/viral:analyze` updates `agent-brain.json` with performance learning weights, closing the `DISCOVER → ANGLE → SCRIPT → POST → ANALYZE` cycle

**State Management:**
- `tracker.py` persists seen content IDs in `data/recon/tracker-state.json` to avoid duplicate processing
- `state_manager.py` persists job states as JSON files in `data/recon/state/`
- SQLite database at `data/recon/recon.db` for asset management (org mode for saved assets)

## Entry Points

| Entry Point | Path | Trigger |
|---|---|---|
| Claude Command (7) | `.claude/commands/viral-*.md` | User types `/viral:*` in Claude Code |
| Recon UI (Flask) | `recon/web/app.py` main() | `bash scripts/run-recon-ui.sh` or `python -m recon.web.app` |
| Topic rescore CLI | `scoring/rescore.py` main | `python scoring/rescore.py [file]` |
| PDF generator | `scripts/generate-pdf.py` | `python scripts/generate-pdf.py --script-id X` |
| Bootstrap | `scripts/init-viral-command.sh` | `bash scripts/init-viral-command.sh` |
| Installation | `install.sh` | `bash <(curl -fsSL ...)` |
| Cron automation | N/A | `docs/CRON-SETUP.md` details daily+weekly cron jobs |

## Module Boundaries & Coupling

| Depender | Depends on | For |
|---|---|---|
| `recon.bridge` | `scoring.engine` (via `sys.path` insert) | Topic scoring during skeleton→topic conversion |
| `recon.skeleton_ripper.pipeline` | `recon.scraper.instagram`, `recon.scraper.downloader`, `recon.config` | Instagram scraping + transcription |
| `recon.skeleton_ripper.extractor` | `recon.skeleton_ripper.llm_client`, `recon.skeleton_ripper.prompts` | LLM extraction calls |
| `recon.skeleton_ripper.synthesizer` | `recon.skeleton_ripper.llm_client`, `recon.skeleton_ripper.aggregator` | Pattern synthesis |
| `recon.web.app` | `recon.config`, `recon.scraper.*`, `recon.skeleton_ripper.*`, `recon.bridge`, `recon.storage.database` | Full frontend integration |
| `scoring.engine` | No `recon/*` imports | Purity — only reads `agent-brain.json` |
| `scripts/*.py` | External APIs (requests, Google API, ReportLab) | Standalone utilities |
| `skills/last30days/` | Bundled skill — independent of `recon/` and `scoring/` | Self-contained research |

## Configuration & Environment

**Environment Configuration:**
- API keys stored in `.env` (gitignored) — read by `recon/config.py` via `load_credentials()` which checks env vars first, then `.env.example` shipped with empty stubs
- Secondary fallback: `data/recon/.credentials` file for non-env-variable config
- Agent brain at `data/agent-brain.json` (git-tracked) contains ICP, pillars, platforms, competitors, learning weights — all non-secret configuration

**Build:**
- `requirements.txt` — Python deps (Flask, requests, yt-dlp, reportlab, google-api-client, python-dotenv)
- Optional: `instaloader` (IG scraping), `openai-whisper` (local transcription) — commented out in requirements, installed separately

**Platform Requirements:**
- Python 3.8+ (recommended 3.10+)
- Node.js 18+
- Claude Code CLI
- CLI tools: `yt-dlp`, `instaloader` (installed via pip)
- OpenAI API key (for Whisper transcription), YouTube Data API v3 key (for discovery + analytics)

## Error Handling

**Strategy:** Structured error tracking via custom logger in `recon/utils/logger.py` — generates unique error codes (`CATEGORY-TIMESTAMP-HASH`), writes JSONL-structured logs to `data/recon/logs/`, separates errors into `errors.log`, supports error registry lookup.

**Patterns:**
- Retry with exponential backoff + jitter via `recon/utils/retry.py` — pre-configured `network_retry` and `api_retry` decorators
- LLM client retries on 429/5xx/connection errors with configurable max retries
- Transcription retries with backoff for both OpenAI API and local Whisper
- Batched extraction with binary-split retry on parse failures
- Pipeline failure handling captures errors per creator, continues processing remaining creators
- Thread-based async job execution in web UI with polling via `/api/jobs/{id}/status`

## Cross-Cutting Concerns

**Logging:** `recon/utils/logger.py` — Singleton `ReconLogger` with structured JSON output, file rotation (10MB, 5 files), colorized console output, error code generation, thread safety

**Validation:** JSON Schema draft-07 in `schemas/` folder for all data entities (agent-brain, topic, hook, angle, script, etc.) with `additionalProperties: false` enforcement

**Authentication:** Credentials via environment variables → `.env` file → `.credentials` file cascade. Claude commands never store keys in tracked files. OAuth tokens stored at `~/.viral-command/` for YouTube Analytics.

**Deduplication:** `recon/tracker.py` maintains `data/recon/tracker-state.json` — maps `{competitor_handle: {content_id: timestamp}}` with stale detection (24h default) and cleanup (30-day retention).

---

*Architecture analysis: 2026-07-09*