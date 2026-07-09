# Codebase Structure

**Analysis Date:** 2026-07-09

## Directory Layout

```
goviralbro/
├── .claude/
│   └── commands/              # Claude Code /viral:* command definitions (Markdown)
│       ├── viral-setup.md         # Platform connection & dependency wizard
│       ├── viral-onboard.md       # Interactive agent brain setup
│       ├── viral-discover.md      # Topic discovery + competitor scraping
│       ├── viral-angle.md         # Contrast Formula angle development
│       ├── viral-script.md        # Script & hook generation
│       ├── viral-analyze.md       # Multi-platform analytics + brain update
│       └── viral-update-brain.md  # Brain evolution protocol
│
├── .planning/                  # GSD planning directory (codebase maps)
│   └── codebase/
│       ├── ARCHITECTURE.md
│       └── STRUCTURE.md
│
├── assets/                     # Brand assets
│   ├── gvb-logo.svg
│   └── install-preview.svg
│
├── data/                       # Runtime data (persistent, evolving)
│   ├── agent-brain.json            # Central evolving system memory
│   ├── cta-templates.json          # Platform-specific CTA templates
│   ├── topics/                     # Discovered topics (date-stamped JSONL)
│   ├── hooks/                      # Hook repository
│   ├── angles/                     # Angle development storage
│   ├── insights/                   # Aggregated performance insights
│   ├── analytics/                  # Performance data
│   │   └── raw/                    # Raw analytics pull data
│   └── recon/                      # Recon module data
│       ├── competitors/            # Per-handle scraped reels/videos JSON
│       ├── reports/                # Skeleton ripper timestamped reports
│       ├── cache/                  # Transcript cache files
│       ├── logs/                   # Structured JSON logs
│       └── state/                  # Job state files
│
├── docs/                       # Documentation
│   └── CRON-SETUP.md               # Automated cron job setup guide
│
├── recon/                      # Competitor intelligence module (Ported from ReelRecon)
│   ├── __init__.py                 # Module doc + usage examples
│   ├── config.py                   # Competitor loading, credential management
│   ├── tracker.py                  # Content deduplication state
│   ├── bridge.py                   # Skeleton→topic conversion + scoring bridge
│   │
│   ├── scraper/                    # Platform scrapers
│   │   ├── __init__.py
│   │   ├── instagram.py            # Instaloader-based IG scraper (242 lines)
│   │   ├── youtube.py              # yt-dlp-based YouTube scraper (194 lines)
│   │   └── downloader.py           # Video download + transcription (224 lines)
│   │
│   ├── skeleton_ripper/            # Content pattern analysis pipeline
│   │   ├── __init__.py             # Public API exports
│   │   ├── pipeline.py             # 4-stage pipeline orchestration (431 lines)
│   │   ├── extractor.py            # Batch LLM skeleton extraction (142 lines)
│   │   ├── aggregator.py           # Statistical aggregation (117 lines)
│   │   ├── synthesizer.py          # LLM pattern synthesis (130 lines)
│   │   ├── llm_client.py           # Multi-provider LLM client (203 lines)
│   │   ├── prompts.py              # Prompt templates + validation (202 lines)
│   │   └── cache.py                # Transcript disk caching (98 lines)
│   │
│   ├── storage/                    # SQLite-based asset management
│   │   ├── __init__.py
│   │   ├── database.py             # SQLite init + connection (104 lines)
│   │   └── models.py               # Asset/Collection dataclasses + CRUD (195 lines)
│   │
│   ├── utils/                      # Shared utilities
│   │   ├── __init__.py
│   │   ├── logger.py               # Singleton structured logger (197 lines)
│   │   ├── retry.py                # Exponential backoff decorator (109 lines)
│   │   └── state_manager.py        # Lightweight JSON state persistence (57 lines)
│   │
│   └── web/                        # Flask web UI
│       ├── __init__.py
│       ├── app.py                  # Flask app: routes + API + main (382 lines)
│       ├── static/
│       │   ├── css/tactical.css    # Dashboard styling
│       │   └── js/app.js           # Shared JS utilities (26 lines)
│       └── templates/
│           ├── competitors.html    # Competitor dashboard (203 lines, inline JS)
│           ├── skeleton_ripper.html# Analysis control page
│           └── settings.html       # Credential configuration page
│
├── schemas/                     # JSON Schema draft-07 contracts (10 files)
│   ├── agent-brain.schema.json      # Central brain schema (342 lines)
│   ├── topic.schema.json            # Discovered topic schema (103 lines)
│   ├── hook.schema.json             # HookGenie output schema (104 lines)
│   ├── angle.schema.json            # Angle development schema
│   ├── script.schema.json           # Generated script schema
│   ├── swipe-hook.schema.json       # Competitor swipe hook schema
│   ├── insight.schema.json          # Performance insight schema
│   ├── analytics-entry.schema.json  # Analytics entry schema
│   ├── competitor-reel.schema.json  # Competitor reel/video schema
│   └── agent-brain.schema.json      # Agent brain schema
│
├── scoring/                     # Topic scoring engine (stdlib only)
│   ├── __init__.py               # Public API exports
│   ├── engine.py                  # 4-criteria scorer + weighting (292 lines)
│   └── rescore.py                 # CLI batch rescore tool (132 lines)
│
├── scripts/                     # Entry points & automation (8 scripts)
│   ├── init-viral-command.sh       # Bootstrap script (303 lines)
│   ├── run-recon-ui.sh             # Flask UI launcher (39 lines)
│   ├── generate-pdf.py             # PDF lead magnet generator (309 lines)
│   ├── fetch-yt-analytics.py       # YouTube Analytics fetcher (296 lines)
│   ├── fetch-ig-insights.py        # Instagram Insights fetcher (285 lines)
│   ├── setup-yt-oauth.py           # YouTube OAuth setup
│   ├── setup-ig-token.py           # Instagram Graph API token setup
│   ├── init-data.sh                # Data directory initialization
│   └── refresh-ig-token.sh         # Instagram token refresh utility
│
├── skills/
│   └── last30days/                  # Bundled research skill
│       ├── SKILL.md                # Skill definition & workflow
│       ├── SPEC.md                 # Technical specification
│       ├── README.md               # Skill documentation
│       ├── CHANGELOG.md            # Version history
│       ├── agents/
│       │   └── openai.yaml         # OpenAI agent config
│       ├── fixtures/               # Test data samples (5 JSON files)
│       ├── scripts/
│       │   ├── last30days.py       # Main research engine
│       │   ├── briefing.py         # Briefing generation
│       │   ├── store.py            # Watchlist storage
│       │   ├── watchlist.py        # Watchlist management
│       │   ├── sync.sh             # Sync utility
│       │   └── lib/                # Library modules (20+ .py files)
│       │       ├── bird_x.py, xai_x.py           # X/Twitter search
│       │       ├── openai_reddit.py, reddit_enrich.py  # Reddit search
│       │       ├── youtube_yt.py                  # YouTube search
│       │       ├── brave_search.py, websearch.py  # Web search
│       │       ├── parallel_search.py             # Parallel execution
│       │       ├── models.py, schema.py           # Data models
│       │       ├── score.py, dedupe.py             # Scoring/dedup
│       │       ├── cache.py, dates.py              # Caching/dates
│       │       ├── entity_extract.py, render.py    # Entities/rendering
│       │       ├── env.py, http.py, ui.py          # Utilities
│       │       └── vendor/bird-search/            # Vendored X client
│       └── tests/                  # Unit tests (8 test files)
│           ├── test_cache.py, test_dates.py, test_dedupe.py
│           ├── test_models.py, test_normalize.py
│           ├── test_openai_reddit.py, test_render.py, test_score.py
│
├── config files:
│   ├── requirements.txt         # Python dependencies (12 lines)
│   ├── .env.example            # API key template (git-tracked)
│   ├── .gitignore
│   ├── LICENSE                  # MIT
│   ├── README.md                # Project overview (134 lines)
│   ├── SETUP.md                 # Detailed setup guide (233 lines)
│   ├── CONTRIBUTING.md          # Contribution guidelines
│   └── install.sh               # One-line curl-bash installer (71 lines)
```

## Key Files (with purposes)

### Core Data Files

| File | Purpose
|---|---|
| `data/agent-brain.json` | Central system memory — identity, ICP, pillars, competitors, learning weights, monetization strategy, performance patterns. Read by `scoring/engine.py` and `recon/config.py`. Updated by `/viral:onboard` and `/viral:analyze`. |
| `data/cta-templates.json` | 143-line library of platform-specific CTA templates for YouTube (longform/shorts), Instagram Reels, TikTok, and LinkedIn — 6 CTA types (community, lead_magnet, website, dm, booking, product) per platform. |
| `schemas/topic.schema.json` | Topic data contract — id, title, description, source, scoring (4 criteria + weighted_total), pillars, competitor_coverage, status, notes. |
| `schemas/agent-brain.schema.json` | Comprehensive 342-line schema defining brain structure with 12 required top-level sections. |
| `schemas/hook.schema.json` | HookGenie output schema — 6 patterns, composite scoring with weighted sub-scores, lifecycle status, performance tracking. |

### Recon Module Core Files

| File | Lines | Purpose
|---|---|---|
| `recon/web/app.py` | 382 | Flask dashboard: 3 pages + 8 API endpoints for scraping, skeleton analysis, settings, push-to-discover bridge |
| `recon/skeleton_ripper/pipeline.py` | 431 | 4-stage pipeline: scrape+transcribe → extract → aggregate → synthesize. Handles Instagram via Instaloader. |
| `recon/skeleton_ripper/prompts.py` | 202 | Prompts for skeleton extraction (batch mode) and pattern synthesis. Validation functions for skeleton fields. |
| `recon/skeleton_ripper/llm_client.py` | 203 | Multi-provider LLM client (OpenAI, Anthropic, Google, Ollama) with retry logic and provider detection. |
| `recon/scraper/instagram.py` | 242 | Instaloader client with session persistence, competitor reel fetching, save/load from `data/recon/competitors/` |
| `recon/scraper/youtube.py` | 194 | yt-dlp-based YouTube scraper — channel video listing, video download, data persistence |
| `recon/scraper/downloader.py` | 224 | OpenAI Whisper API transcription + local Whisper fallback + direct URL download with retries |
| `recon/bridge.py` | 244 | Converts skeleton analysis → scored topics for the discovery pipeline. Key integration point. |
| `recon/config.py` | 129 | Configuration loader — reads `agent-brain.json` for competitors, cascades credentials: env vars → `.env` → `.credentials` file |
| `recon/tracker.py` | 141 | Content deduplication — tracks seen content by handle+content_id, stale detection, cleanup |
| `recon/storage/models.py` | 195 | Asset/Collection dataclasses with full CRUD operations on SQLite |
| `recon/utils/logger.py` | 197 | Singleton structured JSON logger with file rotation, error codes, thread safety |

### Scoring Module Core Files

| File | Lines | Purpose
|---|---|---|
| `scoring/engine.py` | 292 | 4-criteria topic scorer — ICP relevance, timeliness, content gap, proof potential. Read-only on `agent-brain.json`. Competitor bonuses for high-view content. No external dependencies. |
| `scoring/rescore.py` | 132 | CLI tool to recompute `weighted_total` for existing topics when brain weights change. |

### Utilities & Scripts

| File | Lines | Purpose
|---|---|---|
| `scripts/fetch-yt-analytics.py` | 296 | YouTube per-video analytics (CTR, watch time, display time, subs gained) — combines Data API v3 + Analytics API |
| `scripts/fetch-ig-insights.py` | 285 | Instagram per-post insights via Graph API (views, reach, saves, likes, comments, engagement) |
| `scripts/generate-pdf.py` | 309 | PDF lead magnet generation from scripts using ReportLab |
| `scripts/init-viral-command.sh` | 303 | Bootstrap script — creates directories, init data files, installs deps, configures Claude command symlinks |

## Module Map

### `recon` package (`recon/`)
- **Description**: Competitor content intelligence — scrape, transcribe, extract skeletons, synthesize patterns, bridge to discovery
- **Exports**: `config`, `bridge`, `tracker`, `scraper.*`, `skeleton_ripper.*`, `storage.*`, `utils.*`, `web.app`
- **Dependencies**: `instaloader`, `yt-dlp`, `requests`, `Flask`, `sqlite3`, OpenAI/Anthropic/Google LLM APIs
- **Sub-packages**: `scraper/` (3 files), `skeleton_ripper/` (7 files), `storage/` (2 files), `utils/` (3 files), `web/` (6 files + templates)

### `scoring` package (`scoring/`)
- **Description**: Topic scoring against agent brain — pure computation, no external deps
- **Exports**: `engine.score_topic()`, `engine.load_brain_context()`, `rescore.rescore_topics()`
- **Dependencies**: `agent-brain.json` (read-only), stdlib only
- **Design constraint**: Explicitly does NOT import from `recon/` — maintains layer purity

### `scripts/` directory
- **Description**: Standalone CLI entry points and automation
- **No package**: Each is a top-level executable script
- **Dependencies**: Varies per script — `requests`, `google-api-client`, `reportlab`, etc.

### `skills/last30days/` directory
- **Description**: Self-contained research skill for topic discovery across Reddit/X/YouTube/web
- **Exports**: `scripts/last30days.py` (main engine), `scripts/lib/*.py` (20 modules)
- **Dependencies**: `node` (for bird-search vendored X client), OpenAI API, various search APIs
- **Test coverage**: 8 test files in `tests/`

## File Size & Complexity Hotspots

**Largest source files (top 10):**

| File | Lines | Complexity |
|---|---|---|
| `recon/skeleton_ripper/pipeline.py` | 431 | High — 4-stage pipeline orchestration, Instaloader integration, cache logic, progress callbacks, output generation |
| `recon/web/app.py` | 382 | High — 8 API endpoints, threading for async jobs, Flask routes, multiple API integrations |
| `scripts/generate-pdf.py` | 309 | Medium — ReportLab PDF generation, script parsing, template rendering |
| `scripts/init-viral-command.sh` | 303 | Medium — bash bootstrap with colored output, dependency detection, symlink management |
| `scoring/engine.py` | 292 | High — 4 scoring algorithms, stem matching, keyword extraction, competitor bonuses |
| `scripts/fetch-yt-analytics.py` | 296 | Medium — YouTube Data API + Analytics API multi-endpoint data fetching |
| `scripts/fetch-ig-insights.py` | 285 | Medium — Instagram Graph API multi-endpoint analytics fetching |
| `recon/skeleton_ripper/llm_client.py` | 203 | Medium — 4 provider implementations, retry logic, provider config + detection |
| `recon/skeleton_ripper/prompts.py` | 202 | Medium — 2 major prompt templates with formatting, validation functions |
| `recon/utils/logger.py` | 197 | Medium — singleton logger with JSON output, rotation, error registry |

**Complexity hotspots:**
- `recon/skeleton_ripper/pipeline.py` is the most complex file — orchestrates 4 stages with progress tracking, error handling per-creator, Instaloader setup, Whisper fallback, transcript caching, and output writing
- `recon/web/app.py` is a monolith Flask app — routes, API endpoints, job management all in one file; no blueprint separation
- `recon/config.py` and `recon/bridge.py` both use `sys.path` manipulation (anti-pattern) to import from sibling `scoring/` package
- `recon/skeleton_ripper/llm_client.py` has 4 provider implementations in one class — could benefit from a provider strategy pattern

## Naming Conventions

**Files:**
- Python: `snake_case.py` (e.g., `instagram.py`, `skeleton_ripper.py`, `generate-pdf.py`)
- Shell: `kebab-case.sh` (e.g., `init-viral-command.sh`, `run-recon-ui.sh`)
- JSON Schema: `kebab-case.schema.json` (e.g., `agent-brain.schema.json`)
- Data: `date-prefixed.jsonl` (e.g., `20260304-topics.jsonl`)
- Claude commands: `viral-kebab-case.md` (e.g., `viral-setup.md`, `viral-analyze.md`)

**Directories:**
- Single lowercase word: `recon/`, `scoring/`, `schemas/`, `scripts/`, `assets/`, `data/`, `docs/`

**Functions/Classes:**
- Python: `snake_case` functions (e.g., `load_competitors`, `generate_topics_from_skeletons`), `PascalCase` classes (e.g., `SkeletonRipperPipeline`, `BatchedExtractor`)
- Module `__init__.py` exports follow `ALL_CAPS` `__all__` list pattern

## Where to Add New Code

**New Feature (e.g., new platform scraper):**
- Platform scraper: `recon/scraper/{platform}.py`
- Plus update `recon/scraper/__init__.py` exports
- Plus update `recon/config.py` if new credential type needed
- Tests: Not yet established — no test directory exists for `recon/` or `scoring/`

**New API endpoint (for Recon UI):**
- Route definition: `recon/web/app.py`
- Logic: either inline or extract to new module in `recon/`

**New data entity:**
- JSON Schema: `schemas/{entity}.schema.json`
- Data storage: add to appropriate `data/` subdirectory

**New scoring criterion:**
- Add scoring function: `scoring/engine.py`
- Update `score_topic()` orchestrator
- Update `topic.schema.json`
- Update `agent-brain.schema.json` learning weights if needed

**New utility:**
- `recon/utils/{utility}.py` (for recon-scoped)
- `scripts/{utility}.py` (for standalone CLI)
- `scripts/lib/` (for last30days skill scoped)

**New Claude command:**
- `.claude/commands/viral-{name}.md` with structured sections (Arguments, Rules, Steps)

## Special Directories

**`data/recon/competitors/`:**
- Purpose: Per-competitor scraped content data (reels/videos JSON files)
- Generated: Yes, by scraper modules
- Committed: No — runtime data

**`data/recon/reports/`:**
- Purpose: Skeleton ripper timestamped analysis reports (skeletons.json, synthesis.json, report.md per run)
- Generated: Yes, by `SkeletonRipperPipeline`
- Committed: No

**`data/recon/cache/`:**
- Purpose: Cached transcripts as `.txt` files keyed by `{platform}_{username}_{video_id}.txt`
- Generated: Yes, by transcription pipeline
- Committed: No

**`data/recon/logs/`:**
- Purpose: Structured JSON log files with rotation (`recon.log`, `recon.{n}.log`, `errors.log`)
- Generated: Yes, by `ReconLogger`
- Committed: No

**`skills/last30days/`:**
- Purpose: Bundled third-party skill for cross-platform topic research
- Not generated: vendored/managed in repo
- The `vendor/bird-search/` subdirectory is vendored third-party code (MIT license)

**`.claude/commands/`:**
- Purpose: Claude Code slash-command definitions (Markdown)
- These are not documentation — they are executable prompt templates that Claude runs when the user types `/viral:*`
- The `viral-setup.md` at 732 lines is the largest command

---

*Structure analysis: 2026-07-09*