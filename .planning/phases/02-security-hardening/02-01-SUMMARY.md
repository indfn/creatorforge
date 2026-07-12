---
phase: 02-security-hardening
plan: 01
subsystem: packaging, security, code-cleanup
tags:
  - pyproject.toml
  - env-vars
  - dead-code
  - credentials
requires: []
provides:
  - "Python package definition (pyproject.toml)"
  - "Environment-variable-based credential loading for TTS"
  - "Cleaned downloader module (removed dead wrapper)"
affects:
  - production/AudioGeneration/tts_generation.py
  - agent_core/recon/scraper/downloader.py
tech-stack:
  added:
    - cryptography>=41.0.0 (dependency for Plan 02-02 Fernet encryption)
  patterns:
    - "API credentials read from os.environ.get() with empty-string fallback"
    - "setuptools >=68.0 build backend with find packages"
key-files:
  created:
    - pyproject.toml
  modified:
    - production/AudioGeneration/tts_generation.py
    - agent_core/recon/scraper/downloader.py
decisions: []
metrics:
  duration: "~5 minutes"
  completed_date: "2026-07-12"
---

# Phase 2 Plan 1: Security Hardening & Packaging — Summary

**One-liner:** Created pyproject.toml with setuptools packaging (SEC-05), replaced hardcoded Gemini API key and proxy URL with environment variables (SEC-01), removed dead `transcribe_video_openai` wrapper (SEC-07).

## Tasks Completed

| # | ID | Task | Commit | Status |
|---|----|------|--------|--------|
| 1 | SEC-05 | Create pyproject.toml with proper Python packaging | `5021c56` | ✅ Done |
| 2 | SEC-01 | Replace hardcoded API key and proxy URL with env vars | `12c9414` | ✅ Done |
| 3 | SEC-07 | Remove dead `transcribe_video_openai` wrapper | `5dfb9ee` | ✅ Done |

## Details

### Task 1 — SEC-05: pyproject.toml

Created `pyproject.toml` at project root with:
- **Build system:** setuptools >=68.0, `setuptools.build_meta` backend
- **Project metadata:** `name=creatorforge`, `version=0.1.0`, `requires-python>=3.10`
- **Dependencies:** flask, requests, yt-dlp, reportlab, google-api-python-client, google-auth-oauthlib, google-auth, python-dotenv, jsonschema, portalocker, and **cryptography>=41.0.0** (for Plan 02-02 Fernet encryption)
- **Package discovery:** `include = ["agent_core*", "production*", "scripts*"]`
- **CLI entry points:** `creatorforge-recon` and `creatorforge-tts`
- `requirements.txt` kept in place as loose pin reference

`pip install -e .` succeeds. `from agent_core.recon.config import load_config` and `from agent_core.scoring.engine import score_topic` both import without errors.

### Task 2 — SEC-01: Environment variable credentials

Replaced hardcoded lines in `production/AudioGeneration/tts_generation.py`:

```python
# Before (lines 10-12):
PROXY_URL = "http://127.0.0.1:8317/v1beta/models/gemini-3.1-flash-tts-preview:generateContent"
API_KEY = "your-api-key-3"

# After:
PROXY_URL = os.environ.get("PROXY_URL", "http://127.0.0.1:8317/v1beta/...")
API_KEY = os.environ.get("GEMINI_API_KEY", "")
```

Added validation before payload construction — exits with clear error message if `GEMINI_API_KEY` is not set. The `x-goog-api-key` header mechanism at line 126-127 remains intact; only the value source changed.

### Task 3 — SEC-07: Remove dead code

Removed the `transcribe_video_openai` function (lines 122-124) from `agent_core/recon/scraper/downloader.py`:

```python
# Removed:
def transcribe_video_openai(video_path: str, api_key: str, output_path: Optional[str] = None) -> Optional[str]:
    """Legacy wrapper — calls transcribe_video with OpenAI defaults."""
    return transcribe_video(video_path, api_key=api_key, output_path=output_path)
```

Verified zero callers across `agent_core/`, `production/`, and `scripts/`. The function was a dead compatibility shim with no value over calling `transcribe_video()` directly.

## Deviations from Plan

None — plan executed exactly as written.

## Verification Results

| Check | Result |
|-------|--------|
| `pip install -e .` succeeds | ✅ |
| `import agent_core.recon; import agent_core.scoring; import production` | ✅ |
| No `your-api-key-3` in `tts_generation.py` | ✅ |
| `PROXY_URL` uses `os.environ.get()` pattern | ✅ |
| No references to `transcribe_video_openai` in codebase | ✅ |

## Self-Check: PASSED
