---
phase: code-review
reviewed: 2026-07-09T17:00:00Z
depth: standard
files_reviewed: 13
files_reviewed_list:
  - .env.example
  - recon/config.py
  - recon/skeleton_ripper/llm_client.py
  - recon/skeleton_ripper/pipeline.py
  - recon/scraper/downloader.py
  - recon/web/app.py
  - skills/last30days/scripts/lib/env.py
  - skills/last30days/scripts/lib/models.py
  - skills/last30days/scripts/lib/openai_reddit.py
  - skills/last30days/scripts/lib/openrouter_search.py
  - skills/last30days/scripts/lib/parallel_search.py
  - skills/last30days/scripts/lib/brave_search.py
  - skills/last30days/scripts/lib/xai_x.py
findings:
  critical: 2
  warning: 5
  info: 4
  total: 11
status: issues_found
---

# Code Review Report

**Reviewed:** 2026-07-09T17:00:00Z
**Depth:** standard
**Files Reviewed:** 13
**Status:** issues_found

## Summary

Reviewed 13 files refactored to make hardcoded API provider endpoints configurable via environment variables. The changes span the `recon/` module (LLM client, transcription, config, pipeline, web UI) and the `skills/last30days/` module (all search providers).

**Key concerns:**
1. **CRITICAL:** `NameError` bug in `env.py` — `_PROJECT_ENV` is undefined (typo for `_PROJECT_ENV_FILE`). This will crash `config_exists()` at runtime.
2. **CRITICAL:** Inconsistent `OLLAMA_BASE_URL` defaults between provider config and health check — produces double `/api` paths.
3. Several medium-severity issues: missing trailing-slash sanitation, dead code/imports, settings UI out of sync with new credential model.
4. Backward compatibility for existing `OPENAI_API_KEY` users is maintained via fallback chains in all relevant modules.

---

## Critical Issues

### CR-01: NameError in `config_exists()` — undefined variable `_PROJECT_ENV`

**File:** `skills/last30days/scripts/lib/env.py:134`

**Issue:** The function references `_PROJECT_ENV` which is never defined. The actual variable defined at line 47 is `_PROJECT_ENV_FILE`. Any caller of `config_exists()` will crash with `NameError: name '_PROJECT_ENV' is not defined`.

```python
# Line 47 — CORRECT variable name
_PROJECT_ENV_FILE = (_PROJECT_ROOT / ".env") if _PROJECT_ROOT else None

# Line 134 — TYPO: uses undefined _PROJECT_ENV
def config_exists() -> bool:
    """Check if any configuration file exists."""
    if _PROJECT_ENV and _PROJECT_ENV.exists():  # <-- NameError here
        return True
    return CONFIG_FILE.exists() if CONFIG_FILE else False
```

**Fix:** Replace `_PROJECT_ENV` with `_PROJECT_ENV_FILE`:

```python
def config_exists() -> bool:
    if _PROJECT_ENV_FILE and _PROJECT_ENV_FILE.exists():
        return True
    return CONFIG_FILE.exists() if CONFIG_FILE else False
```

---

### CR-02: Inconsistent `OLLAMA_BASE_URL` defaults cause double path for health check

**File:** `recon/skeleton_ripper/llm_client.py:69` vs `llm_client.py:185`

**Issue:** Two different default values for `OLLAMA_BASE_URL`:
- Provider config (line 69): default `http://localhost:11434/api`
- Health check / `get_available_providers` (line 185): default `http://localhost:11434`

If a user sets `OLLAMA_BASE_URL=http://localhost:11434/api` (matching the provider config default), the health check constructs: `http://localhost:11434/api` + `/api/tags` = `http://localhost:11434/api/api/tags` — a broken URL.

```python
# Line 69
base_url=_env_or_default('OLLAMA_BASE_URL', 'http://localhost:11434/api'),
                                               # ^^^ has /api suffix

# Line 185
_env_or_default('OLLAMA_BASE_URL', 'http://localhost:11434') + '/api/tags',
                                    # ^^^ no /api suffix, then appends /api/tags
```

**Fix:** Use the same default everywhere — recommend `http://localhost:11434` (no `/api` suffix) in both places, and let the `_call_ollama` method add `/api/generate`:

```python
# Line 69 — change to match health check default
base_url=_env_or_default('OLLAMA_BASE_URL', 'http://localhost:11434'),

# Line 170 — update call to include /api prefix
response = requests.post(
    f"{self.config.base_url}/api/generate",  # Add /api here
    ...
)
```

Or alternatively, standardize both on `http://localhost:11434/api` and update line 185:

```python
# Line 185 — strip trailing /api before appending /api/tags
base = _env_or_default('OLLAMA_BASE_URL', 'http://localhost:11434/api')
response = requests.get(base.rstrip('/api') + '/api/tags', timeout=2)
```

---

## Warnings

### WR-01: Missing trailing-slash stripping in `LLMClient._call_openai_compatible`

**File:** `recon/skeleton_ripper/llm_client.py:154`

**Issue:** The `downloader.py` correctly strips trailing slashes from `base_url` (line 63: `.rstrip("/")`) before constructing the API path. The `LLMClient` does not. If a user sets `LLM_BASE_URL=https://api.openai.com/v1/`, the constructed URL becomes `https://api.openai.com/v1//chat/completions` with a double slash.

**Fix:** Strip trailing slash from `base_url` before constructing the path:

```python
def _call_openai_compatible(self, system_prompt, user_prompt, temperature):
    ...
    base_url = self.config.base_url.rstrip("/")
    response = requests.post(
        f"{base_url}/chat/completions",
        ...
    )
```

---

### WR-02: `LLM_ENABLED` defined but never used

**File:** `recon/skeleton_ripper/llm_client.py:33`

**Issue:** The module-level variable `LLM_ENABLED` is computed but never referenced anywhere in the codebase. This is dead code that creates confusion about whether the LLM can be disabled via env var.

```python
LLM_ENABLED = os.getenv("LLM_ENABLED", "true").lower() in ("true", "1", "yes")
```

**Fix:** Either remove the unused variable, or add an `LLM_ENABLED` check in `LLMClient.__init__` or `complete`/`chat` methods:

```python
# Option A: Remove
# LLM_ENABLED = os.getenv("LLM_ENABLED", "true").lower() in ("true", "1", "yes")

# Option B: Use it
def chat(self, ...):
    if not LLM_ENABLED:
        raise RuntimeError("LLM is disabled via LLM_ENABLED=false")
    ...
```

---

### WR-03: `transcribe_video_openai` imported but unused in two files

**File:** `recon/skeleton_ripper/pipeline.py:28`, `recon/web/app.py:24`

**Issue:** The legacy `transcribe_video_openai` wrapper function is imported in both `pipeline.py` and `app.py`, but neither file calls it. The pipeline uses `transcribe_video()` directly (line 312). This is dead code in the imports.

**Fix:** Remove the unused import from both files, or keep it only if future callers are anticipated:

In `pipeline.py`:
```python
from recon.scraper.downloader import (
    transcribe_video,        # keep — used line 312
    # transcribe_video_openai,  # remove — unused
    transcribe_video_local,
    load_whisper_model,
    download_direct,
    WHISPER_AVAILABLE,
)
```

In `app.py`:
```python
from recon.scraper.downloader import transcribe_video  # , transcribe_video_openai  # remove
```

---

### WR-04: Misleading `hasattr` checks in `_scrape_and_transcribe` — fallback never fires

**File:** `recon/skeleton_ripper/pipeline.py:209-210`

**Issue:** `JobConfig` is a dataclass, so `hasattr(config, 'transcribe_base_url')` and `hasattr(config, 'transcribe_model')` are **always `True`** for these defined fields. The `else` branch (env var fallback) is dead code. The code works only because `transcribe_video()` has its own default fallback logic for empty strings.

```python
# Always True for dataclass fields — fallback never fires
transcribe_base_url = config.transcribe_base_url if hasattr(config, 'transcribe_base_url') else os.getenv(...)
transcribe_model = config.transcribe_model if hasattr(config, 'transcribe_model') else os.getenv(...)
```

**Fix:** Replace `hasattr` with a truthiness check so the env fallback actually works when the field is empty:

```python
transcribe_base_url = config.transcribe_base_url or os.getenv('TRANSCRIBE_BASE_URL', 'https://api.openai.com/v1')
transcribe_model = config.transcribe_model or os.getenv('TRANSCRIBE_MODEL', 'whisper-1')
```

---

### WR-05: Settings web UI still references legacy credential keys

**File:** `recon/web/app.py:338-342,352-353`

**Issue:** The settings page and save endpoint still use legacy key names (`openai_api_key`, `anthropic_api_key`, `google_api_key`) instead of the new `llm_api_key` naming. This means:
1. A user who sets `LLM_API_KEY` (the new recommended way) won't see it reflected as "set" in the settings UI.
2. Saving via the settings UI stores keys under the old names, requiring the `load_config()` fallback chain to work.

Also, the default `llm_provider` returned in the settings response is `"openai"` (line 341), but `ReconConfig` defaults to `"custom"`.

```python
# Line 338-341 — still checks old key names
"openai_api_key_set": bool(creds.get("openai_api_key")),
"anthropic_api_key_set": bool(creds.get("anthropic_api_key")),
"llm_provider": creds.get("llm_provider", "openai"),  # default should be "custom"
```

```python
# Line 352-353 — saves old key names, misses llm_api_key
for key in ["ig_username", "ig_password", "openai_api_key", "anthropic_api_key",
            "google_api_key", "llm_provider", "llm_model", "transcribe_provider"]:
```

**Fix:** Update to reflect the new unified credential system:

```python
# In api_get_settings:
return jsonify({
    "ig_username": creds.get("ig_username", ""),
    "ig_password_set": bool(creds.get("ig_password")),
    "llm_api_key_set": bool(creds.get("llm_api_key") or creds.get("openai_api_key")),
    "llm_provider": creds.get("llm_provider", "custom"),  # Updated default
    "llm_model": creds.get("llm_model", "gpt-4o-mini"),
})

# In api_save_settings:
for key in ["ig_username", "ig_password", "llm_api_key", "openai_api_key",
            "llm_provider", "llm_model", "transcribe_provider"]:
    if key in data and data[key]:
        creds[key] = data[key]
```

---

## Info

### IN-01: Unused parameter `mock_models` in `select_xai_model`

**File:** `skills/last30days/scripts/lib/models.py:98`

**Issue:** The `mock_models` parameter is accepted in the signature but never referenced in the function body. Unlike `select_openai_model` (which uses it for mock model listing), `select_xai_model` resolves aliases and doesn't need model lists. However, `get_models()` (line 121) passes `mock_xai_models` to this function, which is silently ignored.

```python
def select_xai_model(
    api_key: str,
    policy: str = "latest",
    pin: Optional[str] = None,
    mock_models: Optional[List[Dict]] = None,  # <-- unused
) -> str:
```

**Fix:** Either remove the parameter to match the function's actual contract, or add a `# noqa` comment to document why it's accepted (e.g., for API consistency with `select_openai_model`):

```python
def select_xai_model(
    api_key: str,
    policy: str = "latest",
    pin: Optional[str] = None,
    mock_models: Optional[List[Dict]] = None,  # kept for API consistency with select_openai_model
) -> str:
```

---

### IN-02: `OLLAMA_BASE_URL` not documented in `.env.example`

**File:** `.env.example`

**Issue:** The `OLLAMA_BASE_URL` env var is used in `recon/skeleton_ripper/llm_client.py` but is not documented in `.env.example`. Users who want to configure a custom Ollama endpoint have no reference for the env var name.

**Fix:** Add an Ollama section to `.env.example`:

```bash
# -- Ollama (local LLM provider) --
# Default: http://localhost:11434
# OLLAMA_BASE_URL=
```

---

### IN-03: Trailing slash breaks model listing URL derivation in `models.py`

**File:** `skills/last30days/scripts/lib/models.py:17-21,27-30`

**Issue:** The URL derivation logic uses `.endswith('/responses')` to detect the Responses API path and replace it with `/models`. If the user sets `OPENAI_REDDIT_BASE_URL=https://api.openai.com/v1/responses/` (with trailing slash), the check fails and falls back to the hardcoded OpenAI URL `https://api.openai.com/v1/models` — even for custom proxies.

**Fix:** Strip trailing slash before the check:

```python
_openai_base = os.getenv("OPENAI_REDDIT_BASE_URL", "https://api.openai.com/v1/responses").rstrip("/")
if _openai_base.endswith('/responses'):
    OPENAI_MODELS_URL = _openai_base.replace('/responses', '/models')
else:
    # Try /v1/models, or fall back
    OPENAI_MODELS_URL = _openai_base.rstrip("/") + "/models"
```

Same pattern for `_xai_base`.

---

### IN-04: `api_run_analysis` does not expose transcribe configuration to web UI users

**File:** `recon/web/app.py:261-266`

**Issue:** The `/api/recon/analyze` endpoint creates a `JobConfig` but only passes `usernames`, `videos_per_creator`, `llm_provider`, and `llm_model`. The `transcribe_*` parameters (`transcribe_api_key`, `transcribe_base_url`, `transcribe_model`) are not read from the request, so web UI users cannot customize transcription behavior. This works only because the pipeline and `transcribe_video()` fall back to env vars.

**Fix:** Either document this limitation, or extend the API route to accept transcribe configuration:

```python
config = create_job_config(
    usernames=usernames,
    videos_per_creator=videos_per_creator,
    llm_provider=llm_provider,
    llm_model=llm_model,
    transcribe_api_key=data.get("transcribe_api_key"),
    transcribe_base_url=data.get("transcribe_base_url"),
    transcribe_model=data.get("transcribe_model"),
)
```

---

_Reviewed: 2026-07-09T17:00:00Z_
_Reviewer: gsd-code-reviewer (standard depth)_
_Depth: standard_
