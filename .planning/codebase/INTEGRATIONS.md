# External Integrations

**Analysis Date:** 2026-07-10

## APIs & External Services

### LLM Providers
- **OpenAI / OpenAI-compatible API** - Chat completions for content skeleton extraction, synthesis, and scoring
  - Endpoint: `{LLM_BASE_URL}/chat/completions` (default: `https://api.openai.com/v1`)
  - Auth: `LLM_API_KEY` or `OPENAI_API_KEY` env var
  - Default model: `gpt-4o-mini`
  - Used by: `agent_core/recon/skeleton_ripper/llm_client.py`, `agent_core/recon/skeleton_ripper/extractor.py`, `agent_core/recon/skeleton_ripper/synthesizer.py`

- **Ollama** - Local LLM alternative
  - Endpoint: `{OLLAMA_BASE_URL}/api/generate` (default: `http://localhost:11434`)
  - Auth: None (local)
  - Default model: `qwen3`
  - Used by: `agent_core/recon/skeleton_ripper/llm_client.py`

### Transcription
- **OpenAI Whisper API** - Audio transcription for competitor videos
  - Endpoint: `{TRANSCRIBE_BASE_URL}/audio/transcriptions` (default: `https://api.openai.com/v1`)
  - Auth: `TRANSCRIBE_API_KEY` or `OPENAI_API_KEY` env var
  - Default model: `whisper-1`
  - Used by: `agent_core/recon/scraper/downloader.py`

- **OpenAI Whisper (local)** - Optional local transcription fallback
  - Auth: None (requires `openai-whisper` pip package)
  - Default model: `small.en`
  - Used by: `agent_core/recon/scraper/downloader.py`

### YouTube
- **YouTube Data API v3** - Video metadata, stats (views, likes, comments, duration, thumbnails)
  - Endpoint: `https://www.googleapis.com/youtube/v3/videos`
  - Auth: `YOUTUBE_DATA_API_KEY` env var (API key)
  - Used by: `scripts/fetch-yt-analytics.py`

- **YouTube Analytics API v2** - CTR, watch time, subscribers gained (OAuth-based)
  - Endpoint: `https://youtubeanalytics.googleapis.com/v2/reports`
  - Auth: OAuth 2.0 (token at `~/.creatorforge/yt-token.json`, setup via `scripts/setup-yt-oauth.py`)
  - Scopes: `yt-analytics.readonly`, `youtube.readonly`
  - Used by: `scripts/fetch-yt-analytics.py`, `agent_core/publishing/oauth.py` (stub), `agent_core/publishing/uploader.py` (stub)

- **yt-dlp (CLI)** - YouTube competitor video metadata fetching and audio download
  - Used for: channel video listing (`--flat-playlist --dump-json`), audio download for transcription
  - Used by: `agent_core/recon/scraper/youtube.py`

### Instagram
- **Instaloader** - Instagram profile/reel scraping (login-based)
  - Auth: Instagram username/password (`IG_USERNAME`, `IG_PASSWORD` env vars)
  - Session persistence: `data/recon/.session_{username}` file
  - Used by: `agent_core/recon/scraper/instagram.py`, `agent_core/recon/skeleton_ripper/pipeline.py`

- **Instagram Graph API (Facebook Graph API v21.0)** - Per-post/reel insights (views, reach, engagement, follower delta)
  - Endpoint: `https://graph.facebook.com/v21.0/{media-id}/insights`
  - Auth: `INSTAGRAM_ACCESS_TOKEN` env var (setup via `scripts/setup-ig-token.py`)
  - Used by: `scripts/fetch-ig-insights.py`

### Text-to-Speech (TTS)
- **Google Gemini 3.1 Flash TTS** - Audio production for video rendering
  - Endpoint: `http://127.0.0.1:8317/v1beta/models/gemini-3.1-flash-tts-preview:generateContent`
  - Auth: `x-goog-api-key` header (`API_KEY` constant in `tts_generation.py`)
  - Voices: `Zephyr` (default), configurable via `channel_config.json`
  - Used by: `production/AudioGeneration/tts_generation.py`

### Web Search (last30days skill - search providers)
- **OpenRouter (Perplexity Sonar Pro)** - Web search via OpenRouter
  - Endpoint: `{OPENROUTER_BASE_URL}/chat/completions` (default: `https://openrouter.ai/api/v1`)
  - Auth: `OPENROUTER_API_KEY` env var
  - Default model: `perplexity/sonar-pro`
  - Used by: `.agents/skills/last30days/` (agent skill)

- **Parallel AI Search** - Web search backend
  - Endpoint: `{PARALLEL_BASE_URL}` (default: `https://api.parallel.ai/v1beta/search`)
  - Auth: `PARALLEL_API_KEY` env var

- **Brave Search** - Web search backend
  - Endpoint: `{BRAVE_BASE_URL}` (default: `https://api.search.brave.com/res/v1/web/search`)
  - Auth: `BRAVE_API_KEY` env var

### X/Twitter Search (last30days skill)
- **xAI API (Grok)** - X/Twitter search via xAI's `x_search` tool
  - Endpoint: `{XAI_BASE_URL}` (default: `https://api.x.ai/v1/responses`)
  - Auth: `XAI_API_KEY` env var
  - Models: grok series (policy: latest)

### OpenAI Responses API (last30days skill)
- **OpenAI Responses API** - Reddit discovery with `web_search` tool
  - Endpoint: `{OPENAI_REDDIT_BASE_URL}` (default: `https://api.openai.com/v1/responses`)
  - Auth: `OPENAI_API_KEY` env var
  - Default model: `gpt-4.1`

## Data Storage

**Databases:**
- SQLite - Local asset/collection storage for Recon UI
  - Database file: `data/recon/recon.db`
  - Client: `sqlite3` (stdlib)
  - ORM: None (raw SQL with FTS5 full-text search)
  - Tables: `assets`, `collections`, `asset_collections`, `assets_fts` (FTS5 virtual table)
  - Used by: `agent_core/recon/storage/database.py`, `agent_core/recon/storage/models.py`

**File Storage:**
- Local filesystem only
  - `data/recon/` - Competitor data, transcripts, logs, caches
  - `data/topics/` - Scored topic JSONL files
  - `data/hooks/` - Hook templates
  - `data/insights/` - Aggregated insights
  - `data/analytics/` - Analytics JSONL files
  - `data/pdfs/` - Generated PDF lead magnets

**Caching:**
- Local filesystem transcript cache at `data/recon/cache/` (`agent_core/recon/skeleton_ripper/cache.py`)
- No external caching service (Redis, Memcached) detected

## Authentication & Identity

**Auth Provider:**
- Custom env-var-based credential management
  - Implementation: `agent_core/recon/config.py` loads from `.env` → env vars with fallback chain
  - Credential storage: `.env` file (project root), `data/recon/.credentials` (legacy fallback)
  - Credential editing UI: Recon web UI at `/settings` (`agent_core/recon/web/app.py`)

**OAuth:**
- Google OAuth 2.0 (Desktop App flow) via `google-auth-oauthlib`
  - Token storage: `~/.creatorforge/yt-token.json`
  - Scopes: `yt-analytics.readonly`, `youtube.readonly`
  - Setup script: `scripts/setup-yt-oauth.py`
  - Client secret required: `scripts/client_secret.json`

## Monitoring & Observability

**Logging:**
- Custom structured JSON logger (`agent_core/recon/utils/logger.py`)
  - Console output (colored, human-readable)
  - File logs at `data/recon/logs/recon.log` with rotation (10MB max, 5 files)
  - Error-only log at `data/recon/logs/errors.log`
  - Thread-safe singleton implementation
  - Error code generation with hex digest for tracking

**Error Tracking:**
- Custom error registry in logger (in-memory, `get_recent_errors()` method)
- No external error tracking service (Sentry, Datadog, etc.)

**Metrics:**
- Not detected

## CI/CD & Deployment

**Hosting:**
- Not configured for production deployment
- Flask dev server (`app.run(host='0.0.0.0', port=5001, debug=True)`) for local-only use

**CI Pipeline:**
- Not detected

## Environment Configuration

**Required env vars:**
| Variable | Purpose | Example Value |
|----------|---------|---------------|
| `OPENAI_API_KEY` | Root API key (fallback for all OpenAI-compatible services) | `sk-...` |
| `LLM_API_KEY` | LLM chat completions | `sk-...` |
| `YOUTUBE_DATA_API_KEY` | YouTube Data API v3 | Google Cloud API key |
| `INSTAGRAM_ACCESS_TOKEN` | Instagram Graph API | Long-lived FB token |
| `INSTAGRAM_BUSINESS_ACCOUNT_ID` | IG business account ID | Numeric string |
| `IG_USERNAME` | Instagram login (Instaloader scraping) | Username |
| `IG_PASSWORD` | Instagram password (Instaloader scraping) | Password |

**Optional env vars:**
| Variable | Default | Purpose |
|----------|---------|---------|
| `LLM_BASE_URL` | `https://api.openai.com/v1` | Custom LLM endpoint |
| `LLM_MODEL` | `gpt-4o-mini` | LLM model name |
| `TRANSCRIBE_BASE_URL` | `https://api.openai.com/v1` | Custom transcription endpoint |
| `TRANSCRIBE_MODEL` | `whisper-1` | Transcription model |
| `TRANSCRIBE_PROVIDER` | `openai` | Transcription provider (`openai`/`local`) |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Local Ollama endpoint |
| `BRAVE_API_KEY` | - | Brave Search API |
| `OPENROUTER_API_KEY` | - | OpenRouter API |
| `PARALLEL_API_KEY` | - | Parallel AI API |
| `XAI_API_KEY` | - | xAI/Grok API |

**Secrets location:**
- `.env` file at project root (gitignored)
- `data/recon/.credentials` (legacy fallback, gitignored)
- `~/.creatorforge/yt-token.json` (YouTube OAuth token, outside repo)
- `scripts/client_secret.json` (Google OAuth client secret, gitignored)

## Webhooks & Callbacks

**Incoming:**
- None detected

**Outgoing:**
- None detected

---

*Integration audit: 2026-07-10*
