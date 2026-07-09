# Technology Stack

**Analysis Date:** 2026-07-09

## Languages

**Primary:**
- **Python 3.10+** — All core modules: recon pipeline (competitor analysis, content skeleton ripper), scoring engine, analytics fetchers, PDF generator, and the `skills/last30days` discovery skill scripts (`requirements.txt`, all `.py` files)

**Secondary:**
- **JavaScript (Node.js 18+)** — Vendored Bird CLI for X/Twitter GraphQL search (`skills/last30days/scripts/lib/vendor/bird-search/bird-search.mjs`)
- **Bash** — Installation scripts, cron setup, data initialization (`install.sh`, `scripts/init-viral-command.sh`, `scripts/init-data.sh`, `scripts/refresh-ig-token.sh`, `scripts/run-recon-ui.sh`, `skills/last30days/scripts/sync.sh`)
- **JSON Schema (draft-07)** — Data contracts for topics, hooks, angles, scripts, analytics, agent brain, swipe hooks, competitor reels (`schemas/*.json`)
- **SVG** — Logo and install preview images (`assets/gvb-logo.svg`, `assets/install-preview.svg`)
- **Markdown** — Claude Code command files (`.claude/commands/viral-*.md`), project documentation

## Runtime

**Environment:**
- **Python 3.10+** runtime for all pipeline execution
- **Node.js 18+** required for X/Twitter Bird search module

**Package Manager:**
- **pip** (Python) — Dependencies in `requirements.txt`
- **npm** (Node.js) — Optional, for Bird CLI if not vendored

## Frameworks

**Core:**
- **Flask >=2.0.0** — Potential API/UI server (imported in `requirements.txt`, not yet used in source files)
- **ReportLab >=4.0.0** — PDF lead magnet generation from scripts (`scripts/generate-pdf.py`)

**Testing:**
- **pytest** — Test suite for `skills/last30days` (`skills/last30days/tests/*.py`)
- **unittest (stdlib)** — Also available as `TestCase` base

**Build/Dev:**
- **yt-dlp >=2023.0.0** — YouTube video metadata extraction, search, and download; used both in main recon module and in `skills/last30days` (at `recon/scraper/youtube.py` and `skills/last30days/scripts/lib/youtube_yt.py`)
- **Instaloader >=4.10** — Instagram profile/reel scraping with session persistence (`recon/scraper/instagram.py`)

## Key Dependencies

### LLM & AI APIs
- `openai` (via `requests`) — GPT chat completions, Whisper audio transcription, OpenAI Responses API for Reddit web search (at `recon/skeleton_ripper/llm_client.py`, `recon/scraper/downloader.py`, `skills/last30days/scripts/lib/openai_reddit.py`)
- `google-generativeai` (via `requests`) — Gemini API for LLM calls (at `recon/skeleton_ripper/llm_client.py`)
- `anthropic` (via `requests`) — Claude API for LLM calls (at `recon/skeleton_ripper/llm_client.py`)
- `ollama` (via `requests`) — Local LLM provider (at `recon/skeleton_ripper/llm_client.py`)
- `openai-whisper>=20231117` — Local Whisper model for offline transcription (optional, at `recon/scraper/downloader.py`)

### Google APIs
- `google-api-python-client>=2.0.0` — YouTube Data API v3 client (`scripts/fetch-yt-analytics.py`)
- `google-auth-oauthlib>=1.0.0` — OAuth 2.0 for YouTube Analytics API
- `google-auth>=2.0.0` — Google Auth library

### Web Scraping & Data Acquisition
- `yt-dlp>=2023.0.0` — YouTube channel scraping, search, download, and transcript extraction (`recon/scraper/youtube.py`, `skills/last30days/scripts/lib/youtube_yt.py`)
- `instaloader>=4.10` — Instagram profile scraping, reel fetching, download with session management (`recon/scraper/instagram.py`)
- `requests>=2.25.0` — HTTP client for all API calls (OpenAI, xAI, Instagram Graph, YouTube, Brave, OpenRouter, Parallel AI, Reddit)

### Data Storage
- `sqlite3` (stdlib) — Database for recon assets and collections (`recon/storage/database.py`, `recon/storage/models.py`)
- `json` (stdlib) — Primary data format for agent brain, credentials, tracker state, and JSONL files
- `pathlib` (stdlib) — Filesystem path management throughout

### PDF Generation
- `reportlab>=4.0.0` — PDF creation from script content (`scripts/generate-pdf.py`)

### Configuration
- `python-dotenv>=1.0.0` — Environment variable loading from `.env` file
- `dataclasses` (stdlib) — Configuration and data model definitions

### ML/AI
- `torch` — Required by openai-whisper for local GPU/CPU inference (`recon/scraper/downloader.py`)
- `whisper` (openai-whisper) — Local speech-to-text model (`recon/scraper/downloader.py`)

## Data Stores

**SQLite:**
- Location: `data/recon/recon.db`
- Purpose: Asset and collection management for recon results (assets table, collections table, asset_collections join, FTS5 full-text search)
- Schema defined in: `recon/storage/database.py`

**JSON Files:**
- `data/agent-brain.json` — Persistent creator profile, ICP, pillars, competitors, learning weights, monetization strategy
- `data/recon/.credentials` — Stored API credentials (env vars take priority)
- `data/recon/tracker-state.json` — Competitor content deduplication tracker

**JSONL Files:**
- `data/hooks.jsonl` — Hook repository
- `data/scripts.jsonl` — Generated scripts
- `data/angles.jsonl` — Developed angles
- `data/analytics/analytics.jsonl` — Performance data
- `data/topics/*.jsonl` — Discovered topics (date-stamped)

**Text Files:**
- `data/recon/cache/*.txt` — Cached transcript files per video

**File System:**
- `data/recon/temp/` — Temporary downloaded videos for transcription
- `data/recon/reports/` — Skeleton analysis reports (JSON + Markdown)
- `data/recon/competitors/` — Per-competitor scraped data
- `data/pdfs/` — Generated PDF lead magnets

## External Services / APIs

| Service | Endpoint/Auth | Used By | Purpose |
|---------|-------------|---------|---------|
| OpenAI API | `api.openai.com` (API key) | `recon/skeleton_ripper/llm_client.py`, `recon/scraper/downloader.py`, `skills/last30days/scripts/lib/openai_reddit.py` | LLM completions, Whisper transcription, Reddit discovery |
| YouTube Data API v3 | `www.googleapis.com/youtube/v3` (API key) | `scripts/fetch-yt-analytics.py` | Video metadata, statistics, thumbnails |
| YouTube Analytics API | `youtubeanalytics.googleapis.com` (OAuth 2.0) | `scripts/fetch-yt-analytics.py` | Watch time, subscribers gained, avg view duration |
| Instagram Graph API | `graph.facebook.com/v21.0` (OAuth token) | `scripts/fetch-ig-insights.py`, `scripts/setup-ig-token.py` | Post insights, reach, engagement, follower data |
| xAI API | `api.x.ai/v1` (API key) | `skills/last30days/scripts/lib/xai_x.py` | X/Twitter search via grok models |
| Anthropic API | `api.anthropic.com/v1` (API key) | `recon/skeleton_ripper/llm_client.py` | Claude LLM completions |
| Google Gemini API | `generativelanguage.googleapis.com/v1beta` (API key) | `recon/skeleton_ripper/llm_client.py` | Gemini LLM completions |
| OpenRouter API | `openrouter.ai/api/v1` (API key) | `skills/last30days/scripts/lib/openrouter_search.py` | Perplexity Sonar Pro web search |
| Parallel AI Search | `api.parallel.ai/v1beta/search` (API key) | `skills/last30days/scripts/lib/parallel_search.py` | Web search with extended excerpts |
| Brave Search API | `api.search.brave.com/res/v1/web/search` (API key) | `skills/last30days/scripts/lib/brave_search.py` | Web and news search |
| Ollama (Local) | `localhost:11434/api` (no auth) | `recon/skeleton_ripper/llm_client.py` | Local LLM inference |
| Reddit JSON | `reddit.com/r/*/.json` (no auth) | `skills/last30days/scripts/lib/reddit_enrich.py` | Thread data with real engagement metrics |
| Twitter/X GraphQL | Bird CLI (browser cookies or auth token) | `skills/last30days/scripts/lib/bird_x.py` | X search via vendored Node.js module |

## Infrastructure / DevOps

**Hosting:**
- No cloud deployment — runs locally via Claude Code CLI

**CI/CD:**
- None detected

**Scheduling:**
- **macOS launchd** — Cron-equivalent for automated daily discovery and weekly analysis (`docs/CRON-SETUP.md`)
- Shell scripts: `docs/CRON-SETUP.md` references `scripts/install-crons.sh` and `scripts/uninstall-crons.sh`

**Platform Requirements:**
- **Claude Code CLI** (latest) — Required for all `/viral:*` command invocations
- Git — Required for cloning/updating
- Works on macOS, Linux, and Windows (via WSL)

## Development Tooling

**Testing:**
- **pytest** — Test runner for `skills/last30days` tests (8 test files covering: OpenAI Reddit, render, dedupe, cache, score, dates, models, normalize)
- **unittest** — Stdlib test framework also importable

**Test Fixtures:**
- `skills/last30days/fixtures/openai_sample.json` — Mock OpenAI API response
- `skills/last30days/fixtures/xai_sample.json` — Mock xAI API response
- `skills/last30days/fixtures/reddit_thread_sample.json` — Mock Reddit thread data
- `skills/last30days/fixtures/models_openai_sample.json` — Mock OpenAI model list
- `skills/last30days/fixtures/models_xai_sample.json` — Mock xAI model list

**Configuration:**
- `.env` / `.env.example` — API keys and environment configuration
- `~/.config/last30days/.env` — Separate config for `skills/last30days`
- `data/agent-brain.json` — Creator profile and system state
- Environment variables: `LAST30DAYS_CONFIG_DIR`, `LAST30DAYS_OUTPUT_DIR`, `LAST30DAYS_CACHE_DIR`, `LAST30DAYS_DEBUG`

---

*Stack analysis: 2026-07-09*
