# Technology Stack

**Analysis Date:** 2026-07-10

## Languages

**Primary:**
- Python 3.10+ - All core engine code, scripts, production pipeline, analytics, scoring, web UI

**Secondary:**
- JavaScript - Jinja2 template expressions in Flask HTML templates (`agent_core/recon/web/templates/`)
- HTML/CSS - Flask UI templates (`agent_core/recon/web/`)

## Runtime

**Environment:**
- Python interpreter (CPython 3.10+)

**Package Manager:**
- pip
- Lockfile: Not detected (only `requirements.txt` with loose pins like `flask>=2.0.0`)

## Frameworks

**Core:**
- Flask 2.0+ (`agent_core/recon/web/app.py`) - Web dashboard/UI for Recon competitor intelligence

**Testing:**
- Not detected (no test framework specified)

**Build/Dev:**
- python-dotenv - Environment variable loading from `.env` file

## Key Dependencies

**Critical:**
- `flask>=2.0.0` - HTTP server for Recon UI dashboard (runs on port 5001)
- `requests>=2.25.0` - HTTP client for all API calls (OpenAI, YouTube, Instagram Graph, Gemini TTS, Ollama)
- `yt-dlp>=2023.0.0` - YouTube video metadata extraction and audio/video downloading
- `instaloader` - Instagram profile/reel scraping (installed via bootstrap script, not in requirements.txt)
- `google-api-python-client>=2.0.0` - YouTube Data API v3 client (OAuth-based analytics)
- `google-auth-oauthlib>=1.0.0` - OAuth 2.0 flow for YouTube Analytics API
- `reportlab>=4.0.0` - PDF lead magnet generation from scripts

**Infrastructure:**
- `python-dotenv>=1.0.0` - `.env` file loading for credentials

**Optional:**
- `openai-whisper>=20231117` - Local audio transcription fallback (requires ffmpeg)
- `faster-whisper>=1.0.0` - Word-level force alignment for animation syncing (not yet implemented)
- `Pillow>=10.0.0` - Fallback image generation (commented out)
- `matplotlib>=3.7.0` - Chart generation (commented out)

## Configuration

**Environment:**
- `.env` file at project root (loaded by `python-dotenv` in `agent_core/recon/config.py` and `scripts/fetch-yt-analytics.py`)
- `.credentials` fallback file at `data/recon/.credentials`
- Legacy `.env` parser in `agent_core/recon/config.py` (`_load_env_file()`) - manual parsing, not relying on python-dotenv library at runtime in recon module

**Key Configs Required:**
- `LLM_API_KEY` / `OPENAI_API_KEY` - LLM chat completions (OpenAI-compatible)
- `YOUTUBE_DATA_API_KEY` - YouTube Data API v3
- `TRANSCRIBE_API_KEY` / `OPENAI_API_KEY` - Audio transcription
- `INSTAGRAM_ACCESS_TOKEN` - Instagram Graph API
- `BRAVE_API_KEY` / `OPENROUTER_API_KEY` / `PARALLEL_API_KEY` - Web search backends
- `XAI_API_KEY` - X/Twitter search (grok models)

**Build:**
- No build system detected

## Platform Requirements

**Development:**
- Python 3.10+
- Node.js 18+ (for OpenCode/Claude Code CLI)
- FFmpeg (for local Whisper transcription)
- yt-dlp CLI (installed by bootstrap script)
- instaloader (installed by bootstrap script)

**Production:**
- No deployment configuration detected

---

*Stack analysis: 2026-07-10*
