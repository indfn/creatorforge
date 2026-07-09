# Integration Points

**Analysis Date:** 2026-07-09

## External APIs

### OpenAI API
- **Endpoints used:**
  - `POST https://api.openai.com/v1/chat/completions` — LLM chat completions (GPT-4o-mini, GPT-4o, GPT-4.1, GPT-5 series)
  - `POST https://api.openai.com/v1/audio/transcriptions` — Whisper audio transcription (model: whisper-1)
  - `POST https://api.openai.com/v1/responses` — Reddit discovery via web_search tool with allowed_domains filter
  - `GET https://api.openai.com/v1/models` — Model list for auto-selection
- **Auth:** Bearer token via `OPENAI_API_KEY` env var
- **Data format:** JSON request/response, multipart form-data for audio uploads
- **Rate limits:** Standard OpenAI tier limits; retry with exponential backoff on 429
- **Files:** `recon/skeleton_ripper/llm_client.py`, `recon/scraper/downloader.py`, `skills/last30days/scripts/lib/openai_reddit.py`, `skills/last30days/scripts/lib/models.py`

### YouTube Data API v3
- **Endpoints used:**
  - `GET https://www.googleapis.com/youtube/v3/videos` — Video statistics, snippet, contentDetails (part=statistics,snippet,contentDetails)
- **Auth:** API key via `YOUTUBE_DATA_API_KEY` env var
- **Data format:** JSON
- **Quota:** 10,000 units/day; 100 units per search, 1 unit per video details request
- **Files:** `scripts/fetch-yt-analytics.py`

### YouTube Analytics API
- **Endpoints used:**
  - `GET https://youtubeanalytics.googleapis.com/v2/reports` — Per-video analytics (estimatedMinutesWatched, averageViewDuration, subscribersGained)
- **Auth:** OAuth 2.0 via `google-auth-oauthlib`; token stored at `~/.viral-command/yt-token.json`
- **Data format:** JSON
- **Files:** `scripts/fetch-yt-analytics.py`, `scripts/setup-yt-oauth.py`

### Instagram Graph API (Facebook)
- **Endpoints used:**
  - `GET https://graph.facebook.com/v21.0/{media-id}` — Media object fields (caption, timestamp, media_type, like_count, comments_count, permalink)
  - `GET https://graph.facebook.com/v21.0/{media-id}/insights` — Reel/Post insights (reach, saved, shares, plays, total_interactions)
  - `GET https://graph.facebook.com/v21.0/{account-id}/media` — Recent media listing
  - `GET https://graph.facebook.com/v21.0/{account-id}/insights` — Account-level follower count insights
- **Auth:** OAuth access token via `INSTAGRAM_ACCESS_TOKEN` env var
- **Data format:** JSON
- **Files:** `scripts/fetch-ig-insights.py`, `scripts/setup-ig-token.py`, `scripts/refresh-ig-token.sh`

### xAI API
- **Endpoints used:**
  - `POST https://api.x.ai/v1/responses` — X/Twitter search via x_search Agent Tools API
  - `GET https://api.x.ai/v1/models` — Model list
- **Auth:** Bearer token via `XAI_API_KEY` env var
- **Data format:** JSON
- **Models:** grok-4-1-fast (latest), grok-4 (stable)
- **Files:** `skills/last30days/scripts/lib/xai_x.py`, `skills/last30days/scripts/lib/models.py`

### Anthropic API
- **Endpoints used:**
  - `POST https://api.anthropic.com/v1/messages` — LLM chat completions (Claude 3 Haiku, Sonnet)
- **Auth:** `x-api-key` header via `ANTHROPIC_API_KEY` env var
- **Data format:** JSON
- **Files:** `recon/skeleton_ripper/llm_client.py`

### Google Gemini API
- **Endpoints used:**
  - `POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent` — LLM completions (Gemini 1.5 Flash, Gemini 1.5 Pro)
- **Auth:** API key via `GOOGLE_API_KEY` env var (passed as query param `?key=`)
- **Data format:** JSON
- **Files:** `recon/skeleton_ripper/llm_client.py`

### OpenRouter API (Perplexity Sonar Pro)
- **Endpoints used:**
  - `POST https://openrouter.ai/api/v1/chat/completions` — Web search via Perplexity Sonar Pro model
- **Auth:** Bearer token via `OPENROUTER_API_KEY` env var
- **Data format:** JSON
- **Headers:** `HTTP-Referer` and `X-Title` for OpenRouter ranking
- **Files:** `skills/last30days/scripts/lib/openrouter_search.py`

### Parallel AI Search API
- **Endpoints used:**
  - `POST https://api.parallel.ai/v1beta/search` — Web search with extended excerpts
- **Auth:** Bearer token via `PARALLEL_API_KEY` env var
- **Data format:** JSON
- **Headers:** `parallel-beta: search-extract-2025-10-10`
- **Files:** `skills/last30days/scripts/lib/parallel_search.py`

### Brave Search API
- **Endpoints used:**
  - `GET https://api.search.brave.com/res/v1/web/search` — Web and news search with freshness filter
- **Auth:** `X-Subscription-Token` header via `BRAVE_API_KEY` env var
- **Data format:** JSON
- **Free tier:** 2,000 queries/month
- **Files:** `skills/last30days/scripts/lib/brave_search.py`

### Ollama (Local)
- **Endpoints used:**
  - `POST http://localhost:11434/api/generate` — Local LLM inference
  - `GET http://localhost:11434/api/tags` — Available model listing
- **Auth:** None (localhost only)
- **Models:** qwen3, llama3, mistral
- **Files:** `recon/skeleton_ripper/llm_client.py`

### Reddit API (Free)
- **Endpoints used:**
  - `GET https://www.reddit.com/r/{subreddit}/search/.json` — Subreddit search (no auth needed)
  - `GET https://www.reddit.com{path}.json?raw_json=1` — Thread data with comments
- **Auth:** User-Agent header only; no API key required
- **Rate limits:** 429 if exceeded; retry with backoff
- **Files:** `skills/last30days/scripts/lib/openai_reddit.py`, `skills/last30days/scripts/lib/reddit_enrich.py`

### Twitter/X GraphQL (via Bird CLI)
- **Method:** Spawns Node.js subprocess (`skills/last30days/scripts/lib/vendor/bird-search/bird-search.mjs`) to call Twitter's internal GraphQL API
- **Auth:** Browser cookies (Safari, Chrome, Firefox) or `AUTH_TOKEN` env var
- **Data format:** JSON via stdout
- **Dependency:** Node.js 22+
- **Files:** `skills/last30days/scripts/lib/bird_x.py`

### Instagram Scraping (Instaloader)
- **Method:** Python library `instaloader` for public profile scraping via simulated mobile app requests
- **Auth:** Instagram username/password login with session persistence (`data/recon/.session_{username}`)
- **Data format:** Python objects serialized to JSON
- **Limitations:** Private profiles not accessible; 2FA not supported; rate limiting possible
- **Files:** `recon/scraper/instagram.py`

## Internal Module Boundaries

### Content Pipeline (Claude Commands)
```
.claude/commands/viral-*.md  (Markdown commands invoked by Claude Code)
        │
        ▼
    scripts/*.py              (Python utility scripts)
    scripts/*.sh              (Shell bootstrap/data init)
        │
        ├──► recon/           (Competitor analysis module)
        │       ├── config.py           ↕ reads    data/agent-brain.json
        │       ├── bridge.py           ↕ writes   data/topics/*.jsonl
        │       ├── tracker.py          ↕ reads    data/recon/tracker-state.json
        │       ├── scraper/
        │       │   ├── instagram.py    ───► Instaloader (external)
        │       │   ├── youtube.py      ───► yt-dlp (subprocess)
        │       │   └── downloader.py   ───► OpenAI Whisper API / local whisper
        │       ├── skeleton_ripper/
        │       │   ├── pipeline.py     ──► orchestrates scrape → transcribe → extract → aggregate → synthesize
        │       │   ├── llm_client.py   ──► OpenAI / Anthropic / Google / Ollama APIs
        │       │   ├── extractor.py    ──► calls LLM via prompts
        │       │   ├── aggregator.py   ──► pure Python aggregation
        │       │   ├── synthesizer.py  ──► calls LLM for pattern synthesis
        │       │   └── cache.py        ──► file-based transcript cache
        │       ├── storage/
        │       │   ├── database.py     ──► SQLite connection/schema
        │       │   └── models.py       ──► CRUD operations on SQLite
        │       └── utils/
        │           ├── logger.py       ──► structured JSON logging to files
        │           ├── retry.py        ──► retry decorator with backoff
        │           └── state_manager.py ──► JSON job state persistence
        │
        ├──► scoring/          (Topic scoring engine)
        │       ├── engine.py           ↕ reads    data/agent-brain.json (read-only)
        │       └── rescore.py          ↕ rewrites data/topics/*.jsonl
        │
        ├──► skills/last30days/ (Bundled research skill)
        │       ├── scripts/last30days.py   ──► main entry point
        │       ├── scripts/briefing.py     ──► weekly insight briefing
        │       ├── scripts/watchlist.py    ──► recurring watchlist
        │       ├── scripts/store.py        ──► data persistence
        │       └── scripts/lib/
        │           ├── openai_reddit.py    ──► OpenAI Responses API for Reddit
        │           ├── xai_x.py            ──► xAI API for X search
        │           ├── bird_x.py           ──► Bird CLI for X search (Node.js)
        │           ├── youtube_yt.py       ──► yt-dlp for YouTube search + transcripts
        │           ├── openrouter_search.py ──► OpenRouter/Perplexity web search
        │           ├── parallel_search.py  ──► Parallel AI web search
        │           ├── brave_search.py     ──► Brave Search API
        │           ├── websearch.py        ──► Assistant web search (Claude WebSearch tool)
        │           ├── reddit_enrich.py    ──► Reddit JSON endpoint for engagement
        │           ├── models.py           ──► Model auto-selection
        │           ├── cache.py            ──► File-based result caching
        │           ├── schema.py           ──► Dataclass schemas
        │           ├── normalize.py        ──► API response normalization
        │           ├── score.py            ──► Scoring algorithm
        │           ├── dedupe.py           ──► Near-duplicate detection
        │           ├── dates.py            ──► Date utilities
        │           ├── entity_extract.py   ──► Entity extraction for supplemental searches
        │           ├── render.py           ──► Markdown report generation
        │           ├── http.py             ──► HTTP client (stdlib only)
        │           ├── env.py              ──► Configuration management
        │           └── ui.py               ──► Terminal UI output
        │
        └──► data/              (JSON/JSONL data stores)
                ├── agent-brain.json        ◄── read by recon, scoring, scripts
                ├── cta-templates.json       ◄── read by script generation
                ├── hooks.jsonl              ◄── read/write by /viral:script
                ├── scripts.jsonl            ◄── read/write by /viral:script, generate-pdf.py
                ├── angles.jsonl             ◄── read/write by /viral:angle
                ├── topics/*.jsonl           ◄── write by bridge.py, read by commands
                ├── analytics/analytics.jsonl ◄── write by /viral:analyze
                ├── insights/insights.json   ◄── write by brain evolution
                ├── recon/recon.db           ◄── SQLite (assets, collections)
                ├── recon/cache/*.txt        ◄── Transcript cache
                └── recon/reports/           ◄── Skeleton analysis outputs
```

### Recon Module ↔ Scoring Module
- **Interface:** `recon/bridge.py` imports `from scoring.engine import score_topic`
- **Data:** `recon/bridge.py` calls `engine_score_topic(title, description, views, timeliness, is_competitor=True)` to score each competitor-derived topic
- **Direction:** recon → scoring (one-way dependency)
- **Contract:** Scoring engine expects `(title: str, description: str, views: int, timeliness: int, is_competitor: bool) → Dict` with score keys

### Recon Module ↔ Skelton Ripper ↔ Scrapers
- **Interface:** `SkeletonRipperPipeline` imports `InstaClient` from `recon.scraper.instagram` and `transcribe_video_openai` / `download_direct` from `recon.scraper.downloader`
- **Data flow:** Scrapers return `List[Dict]` with video metadata → Pipeline downloads → Transcribes via OpenAI/local Whisper → LLM extracts skeletons → Aggregator processes → Synthesizer produces strategy
- **Direction:** Scrapers → Pipeline → Extractor → Aggregator → Synthesizer (linear)

## Data Flow Between Components

### Competitor Discovery Flow
```
Instaloader (IG) / yt-dlp (YT)          External APIs
        │                                       │
        ▼                                       ▼
    Instagram scraper / YouTube scraper     Download video files
    (`recon/scraper/instagram.py`)          (`recon/scraper/downloader.py`)
        │                                       │
        └───────────────┬───────────────────────┘
                        ▼
              OpenAI Whisper API / Local Whisper
              (`recon/scraper/downloader.py`)
                        │
                        ▼
              Transcript cache (file system)
              (`recon/skeleton_ripper/cache.py`)
                        │
                        ▼
              LLM-based Skeleton Extraction
              (`recon/skeleton_ripper/extractor.py`)
              Provider: OpenAI / Anthropic / Google / Ollama
                        │
                        ▼
              Skeleton Aggregation
              (`recon/skeleton_ripper/aggregator.py`)
                        │
                        ▼
              LLM-based Pattern Synthesis
              (`recon/skeleton_ripper/synthesizer.py`)
                        │
                        ▼
              Save reports + skeletons.json
              (`data/recon/reports/`)
                        │
                        ▼
              Bridge → Score + Convert to Topics
              (`recon/bridge.py` → `scoring/engine.py`)
                        │
                        ▼
              Save to JSONL topics file
              (`data/topics/{date}-topics.jsonl`)
```

### Last30Days Research Flow
```
User query: "last30 [topic]"
        │
        ▼
    Config resolution
    (`skills/last30days/scripts/lib/env.py`)
        │
        ├──► OpenAI API (Reddit discovery via Responses API w/ web_search tool)
        │       └──► Reddit enrichment via free JSON endpoint (engagement, comments)
        │
        ├──► xAI API (X/Twitter search via x_search Agent Tools tool)
        │       OR
        │   Bird CLI (X/Twitter search via vendored Node.js Twitter GraphQL)
        │
        ├──► yt-dlp (YouTube search + auto-generated transcript extraction)
        │
        └──► Web Search (Brave / Parallel AI / OpenRouter Sonar Pro)
                │
                ▼
            Normalization → Scoring → Deduplication
            (`normalize.py` → `score.py` → `dedupe.py`)
                │
                ▼
            Markdown report generation
            (`render.py`)
                │
                ▼
            Output to `~/.local/share/last30days/out/`
            (report.md, report.json, raw API responses)
```

### YouTube Analytics Flow
```
/scripts/fetch-yt-analytics.py
        │
        ├──► YouTube Data API v3 (GET /videos?part=statistics,snippet,contentDetails)
        │       Returns: views, likes, comments, duration, title, thumbnail
        │
        └──► YouTube Analytics API (GET /v2/reports) [OAuth required]
                Returns: estimatedMinutesWatched, averageViewDuration, subscribersGained
                │
                ▼
            Merge → Format detection (shortform < 180s vs longform)
            Output: JSON to stdout
```

### Instagram Insights Flow
```
/scripts/fetch-ig-insights.py
        │
        ├──► Instagram Graph API (GET /{media-id})
        │       Returns: caption, timestamp, like_count, comments_count
        │
        ├──► Instagram Graph API (GET /{media-id}/insights)
        │       Returns: reach, saved, shares, plays, total_interactions
        │
        └──► Instagram Graph API (GET /{account-id}/insights)
                Returns: follower_count deltas around publish date
```

### PDF Lead Magnet Generation
```
/scripts/generate-pdf.py
        │
        ├──► Reads data/scripts.jsonl (JSONL)
        ├──► Reads data/agent-brain.json (creator identity, monetization, CTAs)
        │
        └──► ReportLab → Builds PDF with:
                - Page 1: Content items (hooks, value delivery, proof)
                - Page 2: CTA section with funnel URLs and social handles
```

## Configuration / Environment

### Required Environment Variables
| Variable | Source | Purpose |
|----------|--------|---------|
| `OPENAI_API_KEY` | `.env` | Whisper transcription, LLM scoring, Reddit discovery |
| `YOUTUBE_DATA_API_KEY` | `.env` | YouTube analytics and search |

### Optional Environment Variables
| Variable | Source | Purpose |
|----------|--------|---------|
| `ANTHROPIC_API_KEY` | `.env` | Claude LLM for skeleton ripper |
| `GOOGLE_API_KEY` | `.env` | Gemini LLM for skeleton ripper |
| `XAI_API_KEY` | `.env` or `~/.config/last30days/.env` | X/Twitter search |
| `OPENROUTER_API_KEY` | `~/.config/last30days/.env` | Perplexity Sonar Pro web search |
| `PARALLEL_API_KEY` | `~/.config/last30days/.env` | Parallel AI web search |
| `BRAVE_API_KEY` | `~/.config/last30days/.env` | Brave Search API |
| `INSTAGRAM_ACCESS_TOKEN` | `.env` | Instagram Graph API |
| `INSTAGRAM_BUSINESS_ACCOUNT_ID` | `.env` | Instagram business account |
| `INSTAGRAM_APP_ID` | `.env` | Instagram app identifier |
| `INSTAGRAM_APP_SECRET` | `.env` | Instagram app secret |

### Last30Days Skill Configuration
- Config file: `~/.config/last30days/.env` (auto-generated if missing)
- Override: `LAST30DAYS_CONFIG_DIR` env var
- Cache dir: `~/.cache/last30days/` (override: `LAST30DAYS_CACHE_DIR`)
- Output dir: `~/.local/share/last30days/out/` (override: `LAST30DAYS_OUTPUT_DIR`)
- Debug: `LAST30DAYS_DEBUG=1`

### Web Search Backend Priority
1. **Parallel AI** (`PARALLEL_API_KEY`) — highest quality
2. **Brave Search** (`BRAVE_API_KEY`) — 2,000 free queries/month
3. **OpenRouter/Sonar Pro** (`OPENROUTER_API_KEY`) — Perplexity-powered
4. **Claude WebSearch** (built-in) — fallback when no API keys configured

### X/Twitter Source Priority
1. **Bird CLI** (vendored Node.js) — free, uses browser cookies
2. **xAI API** (`XAI_API_KEY`) — paid API with x_search tool

### API Key Validation
- `skills/last30days/scripts/lib/env.py` provides `get_available_sources()` which classifies available sources as: `all`, `both`, `reddit`, `reddit-web`, `x`, `x-web`, `web`, or `none`
- This determines which research sources the last30days pipeline will use

---

*Integration audit: 2026-07-09*
