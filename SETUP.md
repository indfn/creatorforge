# Setup Guide

Detailed installation and configuration for CreatorForge.

---

## Prerequisites

| Tool | Required | Install |
|------|----------|---------|
| OpenCode or Claude Code | Yes | [opencode.ai](https://opencode.ai) or [claude.ai/code](https://claude.ai/code) |
| Python 3.10+ | Yes | `brew install python` (macOS) or [python.org](https://python.org) |
| Node.js 18+ | Yes | `brew install node` (macOS) or [nodejs.org](https://nodejs.org) |
| pip | Yes | Included with Python |
| Git | Yes | `brew install git` (macOS) |

---

## Installation

### 1. Clone the Repository

```bash
git clone <repo-url> creatorforge
cd creatorforge
```

### 2. Run the Bootstrap Script

```bash
bash scripts/init-creatorforge.sh
```

This script is idempotent (safe to run multiple times). It will:
- Create required data directories
- Initialize a default channel (`channels/Default/`)
- Install Python dependencies from `requirements.txt`
- Install CLI tools (`yt-dlp`, `instaloader`) if missing
- Generate a `.env` template if one doesn't exist

### 3. Configure API Keys

The recommended way: run the interactive setup tool:

```bash
python scripts/setup-env.py
```

This walks through each key group (LLM, Groq, YouTube, Instagram, TTS, Pexels, Pixabay, Freesound), opens signup URLs in browser, and saves to `.env`.

To check which keys are still missing without being prompted:

```bash
python scripts/setup-env.py --check
```

**Quick reference:**

| Key | Where to Get It | Free/Paid |
|-----|----------------|-----------|
| `LLM_API_KEY` | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) | 💰 Paid |
| `GROQ_API_KEY` | [console.groq.com/keys](https://console.groq.com/keys) | 🆓 Free (rate-limited) |
| `YOUTUBE_DATA_API_KEY` | [Google Cloud Console](https://console.cloud.google.com/apis/credentials) | 🆓 Free tier (10K quota/day) |
| `GEMINI_API_KEY` | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) | 🆓 Free tier (60 req/min) |
| `PEXELS_API_KEY` | [pexels.com/api](https://www.pexels.com/api/) | 🆓 Free (200 req/hr) |
| `PIXABAY_API_KEY` | [pixabay.com/api/docs](https://pixabay.com/api/docs/) | 🆓 Free (unlimited) |
| `FREESOUND_API_KEY` | [freesound.org/apiv2/apply](https://freesound.org/apiv2/apply/) | 🆓 Free (60 req/min) |

See `.env.example` for all optional keys (research, web search, custom endpoints).

### 4. Verify Connections

```bash
python scripts/doctor.py
```

This checks: project structure, Python/CLI tools, API key presence, credential encryption, OAuth tokens, and network connectivity.

### 5. Back Up Your Encryption Key

The Fernet key at `data/recon/credentials.key` encrypts stored credentials. If lost, they become unrecoverable.

```bash
# Copy key into .env as CREDENTIALS_ENCRYPTION_KEY:
python scripts/backup-credentials-key.py --to-env

# Or export to a file for password manager:
python scripts/backup-credentials-key.py --export > ~/creatorforge-key.txt
```

---

## Platform Connections

### YouTube

**API key (read-only — search + metadata):**
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project and enable **YouTube Data API v3**
3. Create an API key under Credentials
4. Add to `.env` as `YOUTUBE_DATA_API_KEY`

**OAuth (publishing + analytics):**
```bash
# Download client_secret.json from Google Cloud Console first
# then run:
python scripts/setup-yt-oauth.py --channel Default
```
This opens a browser for Google OAuth and saves the token to `channels/Default/yt-oauth-token.json`.

### Instagram

**Graph API (analytics):**
```bash
python scripts/setup-ig-token.py
```
This starts a local server, opens the Facebook OAuth URL, and auto-catches the redirect. Saves `INSTAGRAM_ACCESS_TOKEN` and `INSTAGRAM_BUSINESS_ACCOUNT_ID` to `.env`.

**Public scraping (competitor recon):**
[Instaloader](https://instaloader.github.io/) is used for public profile scraping. No API key needed.

### TikTok / LinkedIn

Analytics entered manually. No API connection required.

### LLM Provider (Content Analysis)

Supports any OpenAI-compatible endpoint. Default: OpenAI.

1. Get an API key: [platform.openai.com](https://platform.openai.com/api-keys)
2. Set `LLM_API_KEY` (or `OPENAI_API_KEY` for backward compat)
3. Optionally set `LLM_BASE_URL` for OpenRouter, Together, Ollama, etc.

### Transcription (Competitor Video Analysis)

Default: **Groq Whisper (free tier)**. Fallback chain: Groq → local faster-whisper.

```bash
# Get a free Groq API key:
# https://console.groq.com/keys
# Add to .env: GROQ_API_KEY=your_key
```

To use OpenAI Whisper instead: set `TRANSCRIBE_API_KEY` + `TRANSCRIBE_BASE_URL`.
To use local Whisper (no API key): set `TRANSCRIBE_PROVIDER=local`.

---

## Cron Setup

For automated daily discovery and weekly analysis, see [docs/CRON-SETUP.md](docs/CRON-SETUP.md).

Quick install (macOS):

```bash
bash scripts/install-crons.sh
```

Quick uninstall:

```bash
bash scripts/uninstall-crons.sh
```

---

## Windows Setup

Windows users should use WSL (Windows Subsystem for Linux):

1. Install WSL: `wsl --install` in PowerShell (admin)
2. Open WSL terminal
3. Follow the Linux/macOS instructions above
4. For cron, see the Windows section in [docs/CRON-SETUP.md](docs/CRON-SETUP.md)

---

## Troubleshooting

### "command not found" for yt-dlp or instaloader

Your shell PATH may not include pip's bin directory. Add to your shell profile (`~/.zshrc` or `~/.bashrc`):

```bash
# macOS with Python.org installer
export PATH="/Library/Frameworks/Python.framework/Versions/3.14/bin:$PATH"

# macOS with Homebrew
export PATH="/opt/homebrew/bin:$PATH"

# Linux / WSL
export PATH="$HOME/.local/bin:$PATH"
```

Then reload: `source ~/.zshrc`

### YouTube API quota exceeded

The YouTube Data API v3 has a daily quota of 10,000 units. Each search costs 100 units, each video details request costs 1 unit. If you hit limits:

- Reduce discovery frequency (skip a day)
- Use `--quick` flag on `/viral:discover` for fewer API calls
- Check quota usage at [Google Cloud Console](https://console.cloud.google.com/apis/dashboard)

### Python dependency conflicts

Use a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Instaloader login issues

Instagram may rate-limit or block unauthenticated requests. If scraping fails:

1. Try logging in: `instaloader --login YOUR_USERNAME`
2. Instaloader stores session cookies locally
3. As a fallback, use `/viral:discover --quick` to skip Instagram sources

### Permission denied on scripts

```bash
chmod +x scripts/*.sh
```

---

## First Run Checklist

After setup, run through the pipeline once to verify everything works:

1. `python scripts/doctor.py` — Verify all checks pass
2. `python scripts/setup-ig-token.py` — Connect Instagram (if needed)
3. `python scripts/setup-yt-oauth.py --channel Default` — Connect YouTube (if needed)
4. `creatorforge doctor` — Final verification

---

## Getting Help

- **GitHub Issues**: Report bugs or request features
- **Skool Community**: [start.ccstrategic.io/skool](https://start.ccstrategic.io/skool)
- **YouTube**: [youtube.com/@charlieautomates](https://youtube.com/@charlieautomates)
