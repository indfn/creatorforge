# Concerns & Improvement Areas

**Analysis Date:** 2026-07-09

## Security

### Hardcoded `.env` files read directly by scripts (high)
- **Location:** `scripts/fetch-ig-insights.py` (lines 42-48), `scripts/fetch-yt-analytics.py` (lines 42-48), `scripts/setup-ig-token.py` (lines 45-51)
- **Issue:** These scripts implement a custom `load_env()` function that reads `.env` line-by-line and sets environment variables via `os.environ.setdefault()`. If `.env` is accidentally committed to version control (it is in `.gitignore`, but a user might force-add it), all API keys, app secrets, and OAuth credentials are exposed. Python's `python-dotenv` is listed in `requirements.txt` but the scripts bypass it, leading to inconsistent env loading patterns.
- **Recommendation:** Use `python-dotenv` consistently across all scripts, or implement a single shared `load_env()` in a central utility module.

### Credentials stored in plaintext `.credentials` file (medium)
- **Location:** `recon/config.py` (lines 16, 63-102)
- **Issue:** The recon module saves credentials (IG username, IG password, OpenAI API key, Anthropic API key, Google API key) to `data/recon/.credentials` as plaintext key=value pairs. A warning comment says "DO NOT COMMIT" but the file exists under `data/recon/` which is gitignored only indirectly via `data/recon/`. If gitignore rules are wrong, this file could leak. Additionally, any process with filesystem access to the data directory can read plaintext API keys.
- **Recommendation:** Store credentials in the OS keychain (keyring library) or encrypt the `.credentials` file with a derived key.

### Flask app runs in debug mode with host 0.0.0.0 (medium)
- **Location:** `recon/web/app.py` (line 378)
- **Issue:** `app.run(host='0.0.0.0', port=5001, debug=True)`. The Flask debug mode exposes a web-based debugger console that can execute arbitrary Python code. Binding to `0.0.0.0` makes this accessible from any network interface. If this is running in a shared or cloud environment, it's a remote code execution vector.
- **Recommendation:** Remove `debug=True` in production. Bind only to `127.0.0.1` or make binding configurable via env var. Use a proper WSGI server (gunicorn/uvicorn) for production.

### API keys passed as command-line parameters in shell scripts (medium)
- **Location:** `scripts/refresh-ig-token.sh` (line 42)
- **Issue:** The Instagram token refresh script passes `$CURRENT_TOKEN` directly as a URL query parameter via `curl`. This exposes the token in process listings (`ps aux`), shell history (though careful with `set -o history`), and debug output. The `-s` flag supresses progress but the URL (including token) is logged in `logs/ig-token-refresh.log`.
- **Recommendation:** Use `curl -sS -o /dev/null` to suppress output. Mask the token in log entries. Consider using the Graph API client SDK instead of raw curl.

### `client_secret.json` gitignored but referenced in code (low)
- **Location:** `scripts/setup-yt-oauth.py` (lines 33, 51), `.gitignore` (line 56)
- **Issue:** Google OAuth `client_secret.json` is correctly gitignored, but if a developer accidentally places it in the wrong location or renames it, the script will fail with a potentially confusing error. No validation message warns about the file location.
- **Recommendation:** Add a startup validation check with clear instructions.

## Technical Debt

### `sys.path.insert(0, ...)` pattern used inconsistently across the project (high)
- **Location:** `recon/web/app.py` (line 19), `recon/bridge.py` (line 18), `scoring/rescore.py` (line 17), and 8 test files in `skills/last30days/tests/`
- **Issue:** Multiple files manipulate `sys.path` at import time to resolve module imports. This is fragile — if the working directory changes or the project structure is refactored (e.g., adding a `src/` layout), imports will silently break. Each occurrence uses a slightly different path calculation, making debugging difficult. This creates an implicit dependency on how the file is invoked (as a script vs. as a module).
- **Estimated effort:** Medium (standardize on relative imports or a proper `setup.py`/`pyproject.toml` install)

### Credential file parsing with no input validation (medium)
- **Location:** `recon/config.py` (lines 72-77)
- **Issue:** The `.credentials` file parser splits on `=` and strips whitespace. If a credential value contains an `=` sign (which is valid in some API keys), the parsing will unexpectedly truncate the value. There is no error if the file is malformed.
- **Estimated effort:** Small (use `partition('=')` instead of `split('=', 1)`, which is already used in scripts — inconsistency across the codebase)

### `app.secret_key` generated randomly on every restart (medium)
- **Location:** `recon/web/app.py` (line 47)
- **Issue:** `app.secret_key = os.urandom(24)` generates a new secret key every time the Flask app starts. This means Flask session cookies signed with the old key will be invalidated on restart. For a local-only UI this is minor, but it indicates sessions don't survive app restarts.
- **Estimated effort:** Small (load a persistent key from a file or env var)

### Scattering of `pass` in exception handlers (low)
- **Locations:** `recon/web/app.py` (line 114), `recon/skeleton_ripper/llm_client.py` (line 196), `recon/skeleton_ripper/extractor.py` (line 141), `recon/utils/state_manager.py` (line 56), `recon/bridge.py` (line 217)
- **Issue:** Several exception handlers silently swallow exceptions with `pass`, making failures invisible to the operator. For example, in `recon/skeleton_ripper/llm_client.py`, the Ollama health check failure is silently ignored; in `recon/web/app.py`, JSON parsing errors while loading competitor data are silently swallowed.
- **Estimated effort:** Small (log each exception before suppressing)

### Copy-pasted port from ReelRecon with "adjusted" comments everywhere (low)
- **Locations:** `recon/scraper/downloader.py` (header), `recon/skeleton_ripper/*.py` (headers), `recon/storage/*.py` (headers), `recon/utils/logger.py` (header), `recon/utils/state_manager.py` (header), `recon/web/app.py` (header)
- **Issue:** Over a dozen files have headers stating "Ported from ReelRecon" with path adjustments. While functional, this indicates significant code reuse without a clear migration strategy. The "unchanged" and "adjusted" comments suggest some code may still have stale ReelRecon references or assumptions.
- **Estimated effort:** Medium (review each ported file for stale references, deduplicate into proper shared modules)

## Performance

### Instagram scraper fetches every post before filtering (high impact)
- **Location:** `recon/scraper/instagram.py` (lines 143-170)
- **Issue:** `profile.get_posts()` iterates through ALL profile posts (including photos, carousels, etc.) to find video/reels. For large accounts with 1000+ posts, this means iterating through all of them even though `max_reels` is usually 50. There is a rate-limiting sleep every 12 items, so scraping a large account is extremely slow. For accounts with mostly photo content, this could waste significant time.
- **Impact:** Slow Instagram scraping for large accounts with low reel density
- **Improvement:** Use Instaloader's `get_posts()` with a target type filter, or check `is_video` earlier in the iteration and break early if the count is met.

### YouTube yt-dlp scraping uses flat playlist but still sequential (medium impact)
- **Location:** `recon/scraper/youtube.py` (lines 56-68)
- **Issue:** Each video fetch runs `yt-dlp` as a subprocess sequentially. For multiple competitors, this becomes serial: fetch channel A, parse output, then fetch channel B, etc. No parallel fetching is used.
- **Impact:** Slow when scanning many competitors (each channel takes 3-10 seconds)
- **Improvement:** Use `concurrent.futures.ThreadPoolExecutor` to fetch multiple channels in parallel.

### yt-dlp audio download always downloads full audio for transcription (medium impact)
- **Location:** `recon/scraper/youtube.py` (lines 138-149)
- **Issue:** Video downloads always grab audio in best available quality (`bestaudio[ext=m4a]/bestaudio/best`). For transcription purposes, a lower quality audio (64kbps) is more than sufficient and would be much faster to download.
- **Impact:** Unnecessarily large downloads for transcription-only workloads
- **Improvement:** Add a quality parameter for transcription-only downloads (e.g., `worstaudio` or format with bitrate limit).

### `recon/config.py` reads `agent-brain.json` on every call to `load_config()` (low impact)
- **Location:** `recon/config.py` (lines 105-119)
- **Issue:** `load_config()` calls `load_competitors()` which reads and deserializes `agent-brain.json` from disk. Every API endpoint that calls `load_config()` (like `/api/competitors/scrape`, `/api/competitors`) incurs a disk read + JSON parse. `load_brain_pillars()` and `load_brain_learning_weights()` in `bridge.py` also re-read the same file independently.
- **Impact:** Small, but cumulative under load
- **Improvement:** Cache `agent-brain.json` in memory with a freshness TTL.

### Duplicate `for line in ENV_PATH.read_text().splitlines()` in three scripts (low)
- **Locations:** `scripts/fetch-ig-insights.py:43`, `scripts/fetch-yt-analytics.py:44`, `scripts/setup-ig-token.py:46`
- **Issue:** Three scripts independently implement identical `.env` parsing logic. This is both a maintenance burden and a performance concern (each reimplements the same function).
- **Impact:** Negligible performance impact, increased maintenance surface
- **Improvement:** Extract to a shared utility module.

## Maintainability

### No test coverage for core `recon` module (high)
- **Location:** Entire `recon/` directory
- **Issue:** The `recon/` module (config, bridge, scraper, skeleton_ripper, storage, utils, web) has zero tests. The only tests in the project exist under `skills/last30days/tests/` which test a different subsystem. The skeleton ripper pipeline (`recon/skeleton_ripper/pipeline.py`, 431 lines) has no unit tests despite its complexity — multiple stages (scrape, transcribe, extract, aggregate, synthesize) with complex error handling and async progress tracking.
- **Why it's hard to maintain:** Changes to the pipeline cannot be validated without running the full flow against real APIs. Refactoring is risky.
- **Priority:** High

### No standalone test runner configuration (high)
- **Location:** Project root
- **Issue:** There is no `pytest.ini`, `setup.cfg`, or `pyproject.toml` with test configuration. Tests exist only under `skills/last30days/tests/`. Running them requires manually setting `PYTHONPATH` and knowing the test directory structure.
- **Why it's hard to maintain:** New developers have no standard way to run tests. CI cannot be configured without discovering the test structure.

### Import path manipulation creates hidden module coupling (high)
- **Locations:** `bridge.py`, `app.py`, `rescore.py`, many `skills/last30days/` files
- **Issue:** The pervasive `sys.path.insert(0, ...)` pattern means module dependencies are resolved at import time based on filesystem layout rather than explicit dependency declarations. Moving a file will break imports silently. The `recon/bridge.py` both imports from `recon.config` (correctly via package) AND uses `sys.path.insert` to import from `scoring.engine` (incorrectly via path hack).
- **Why it's hard to maintain:** Any refactoring (e.g., moving to `src/` layout, renaming packages) requires fixing every `sys.path` insertion point.

### Missing type annotations in multiple files (medium)
- **Locations:** `recon/scraper/youtube.py`, `recon/scraper/downloader.py`, `recon/bridge.py` (partial), `recon/skeleton_ripper/cache.py` (partial), `recon/utils/state_manager.py`
- **Issue:** Many functions lack return type annotations or use `Optional` inconsistently. For example, `recon/scraper/youtube.py` function `save_channel_data` has no return type; `recon/scraper/downloader.py` functions are inconsistently annotated.
- **Why it's hard to maintain:** Refactoring tools cannot detect type errors. New contributors can't infer parameter types from signatures.

### Dead code: `format_aggregation_summary()` function not referenced (low)
- **Location:** `recon/skeleton_ripper/aggregator.py` (lines 106-117)
- **Issue:** The `format_aggregation_summary()` function is defined but never imported or called anywhere in the codebase. It appears to be leftover from the ReelRecon port.
- **Why it's hard to maintain:** Unused code creates confusion about what's actually used.

### Dead code: `schemas/` directory populated but no schema validation performed (low)
- **Locations:** `schemas/agent-brain.schema.json`, `schemas/topic.schema.json`, `schemas/script.schema.json`, `schemas/angle.schema.json`, `schemas/hook.schema.json`, `schemas/insight.schema.json`, `schemas/analytics-entry.schema.json`, `schemas/competitor-reel.schema.json`, `schemas/swipe-hook.schema.json`
- **Issue:** Nine JSON Schema files exist in `schemas/` but no code in the project actually validates any data against these schemas. Comments in `bridge.py` and `__init__.py` files reference schema matching but no validation runtime exists.
- **Why it's hard to maintain:** Schemas and actual data formats can drift silently.

### Broad `except Exception` handlers in critical paths (medium)
- **Locations:** `recon/skeleton_ripper/pipeline.py` (lines 190, 348, 363), `recon/utils/state_manager.py` (line 55), `recon/storage/database.py` (line 100), `recon/web/app.py` (line 113), `recon/skeleton_ripper/llm_client.py` (line 125)
- **Issue:** Several places catch `Exception` broadly with generic handling (log + re-raise, log + ignore, or `pass`). In `pipeline.py` line 190, the entire pipeline failure is caught as a generic `Exception`, losing specific error types. In `state_manager.py` line 55, JSON parsing errors during listing are silently ignored.
- **Why it's hard to maintain:** Specific exception types should be handled differently. Broad catches can mask programming errors.

### The `tracker.py` state file grows unboundedly (medium)
- **Location:** `recon/tracker.py` (lines 119-141)
- **Issue:** The `cleanup_old_entries()` function exists but is never called automatically. The tracker state file (`data/recon/tracker-state.json`) will grow indefinitely as new content is tracked, potentially reaching thousands of entries over time. A 30-day cleanup TTL is defined but never invoked.
- **Why it's hard to maintain:** The state file will eventually become large and slow to load/parse.

## Gaps / Missing Features

### No CI/CD pipeline or automated testing (high)
- **What's missing:** No CI configuration file (`.github/workflows/`, `.gitlab-ci.yml`, etc.). No test runner configuration (`pytest.ini`, `setup.cfg`). No linting configuration (`flake8`, `pylint`, etc.).
- **Why it matters:** Code quality cannot be automatically checked. Breaking changes can be committed without detection. New contributors have no guidance on code quality standards.

### No input validation on the Flask API endpoints (medium)
- **Location:** `recon/web/app.py` (lines 130, 240, 345)
- **Gap:** The `/api/competitors/<handle>/scrape` endpoint takes a `max_reels` from JSON body but does not validate it (could be negative, huge). The `/api/recon/analyze` endpoint accepts `usernames`, `videos_per_creator`, `llm_provider`, `llm_model` without validation against known providers/models. The settings endpoint saves arbitrary credential fields without encryption.
- **Why it matters:** Invalid/malicious input could cause unexpected behavior or crash the pipeline.

### YouTube handle normalization is fragile (medium)
- **Location:** `recon/scraper/youtube.py` (lines 43-48)
- **Gap:** The channel URL construction logic assumes handles start with `@`, fallback to raw, then fallback to `@<handle>/videos`. YouTube handles can have many formats (channel IDs, custom URLs, `/c/` paths). There's no validation that the constructed URL is valid before passing to yt-dlp.
- **Why it matters:** Invalid URLs cause yt-dlp to fail with potentially confusing errors.

### Missing token expiry monitoring for Instagram (medium)
- **Gap:** The Instagram token is only refreshed when `refresh-ig-token.sh` is manually run. There is no automated check or monitoring. The `setup-ig-token.py` notes the token expires in ~60 days but no code warns or auto-refreshes.
- **Why it matters:** Scraping will silently fail mid-job with expired tokens, requiring manual re-setup.

### YouTube Analytics CTR is a documented dead end in code (medium)
- **Location:** `scripts/fetch-yt-analytics.py` (lines 181-212, 267-268)
- **Gap:** The `fetch_ctr()` function explicitly states "YouTube Analytics API does NOT expose thumbnail impression CTR" and the metric is returned as `None` with a note. This is a known feature limitation called out in code comments.
- **Why it matters:** Users expecting full YouTube analytics will find CTR missing with no alternative path.

### No graceful handling for missing `data/agent-brain.json` (medium)
- **Locations:** `scoring/engine.py` (lines 39-50), `recon/config.py` (lines 44-48)
- **Gap:** Both modules handle missing `agent-brain.json` by returning empty/fallback data. However, the system is designed around the agent brain being populated. An empty brain returns ICP scores of 3 (lowest tier) silently with no warning to the user.
- **Why it matters:** Users who skip onboarding will get meaningless scoring with no indication why.

### No pagination or cleanup for the UI's `active_jobs` dictionary (medium)
- **Location:** `recon/web/app.py` (line 53)
- **Gap:** `active_jobs = {}` is an in-memory dict that grows unboundedly. Completed and errored jobs are never removed. Over time (or with concurrent usage), this will consume increasing memory.
- **Why it matters:** Memory leak in long-running UI sessions.

### Missing error handling for yt-dlp format selection failure (low)
- **Location:** `recon/scraper/youtube.py` (line 143, format string)
- **Gap:** The download format `bestaudio[ext=m4a]/bestaudio/best` may fail if no audio track exists (rare but possible). There's no fallback format.

## Redundancy / Duplication

### Three implementations of `.env` file parsing
- **Locations:** `scripts/fetch-ig-insights.py` (lines 40-48), `scripts/fetch-yt-analytics.py` (lines 40-48), `scripts/setup-ig-token.py` (lines 45-51)
- **Details:** All three implement the exact same `load_env()` logic (read `.env`, split lines by `=`, skip comments, call `os.environ.setdefault`). The `setup-ig-token.py` variant also duplicates the `update_env()` function for writing back to `.env`.

### Inconsistent path calculation for data directories
- **Locations:** `recon/config.py` (line 13: `Path(__file__).parent.parent`), `recon/bridge.py` (line 23: `Path(__file__).parent.parent`), `recon/tracker.py` (line 13: `Path(__file__).parent.parent`), `recon/web/app.py` (lines 36-38: `BASE_DIR.parent.parent`), `recon/scraper/instagram.py` (line 25: `.parent.parent.parent`), `recon/scraper/youtube.py` (line 23: `.parent.parent.parent`), etc.
- **Details:** Every module independently recalculates the project root path using different numbers of `.parent` calls. If the directory structure changes (e.g., adding a `src/` wrapper), every one of these must be updated individually.

### Repeated view-count sorting logic
- **Locations:** `recon/scraper/instagram.py` (lines 173-174), `recon/scraper/youtube.py` (lines 98-99), `recon/skeleton_ripper/pipeline.py` (does not sort — inconsistency)
- **Details:** Both Instagram and YouTube scrapers implement identical `sort(key=lambda x: x.get("views", 0), reverse=True)` but the Instagram scraper normalizes `views` field while YouTube uses raw `view_count`. The pipeline does not sort at all.

### Google API key stored in `QUERY STRING` (Google convention) vs header (industry standard)
- **Location:** `recon/skeleton_ripper/llm_client.py` (line 162)
- **Issue:** The Google Gemini API key is passed as a URL query parameter: `?key={self.api_key}`. While this is the documented Google approach, it exposes the key in URL logs, server access logs, and browser history if debugging.

## Fragility / Risk Areas

### Instagram scraping reliability depends on Instaloader + account health (critical)
- **Locations:** `recon/scraper/instagram.py`, `recon/skeleton_ripper/pipeline.py` (lines 215-223)
- **Why fragile:** The entire Instagram competitor analysis pipeline requires a working Instaloader session with a valid Instagram login. Instagram aggressively rate-limits and bans automated access. Session files can expire, IPs can be blocked, 2FA accounts can't be used, and platform changes (API updates) can break Instaloader entirely. There is no graceful degradation path for when Instagram scraping fails — the pipeline throws `RuntimeError`.

### Subprocess calls to yt-dlp without timeout on parse (medium)
- **Location:** `recon/scraper/youtube.py` (lines 56-69)
- **Why fragile:** The `subprocess.run()` has a 120-second timeout, but if yt-dlp outputs a large amount of data (e.g., for a channel with 1000s of videos and `--flat-playlist`), stdout parsing could be slow. The `result.stdout.strip().split("\n")` could produce a large (5000+ items) list that is then processed sequentially.

### Multi-provider LLM client has no request retry abstraction (medium)
- **Location:** `recon/skeleton_ripper/llm_client.py`
- **Why fragile:** The `chat()` method has retry logic, but the `_call_openai`, `_call_anthropic`, `_call_google`, `_call_ollama` methods each format requests differently and handle errors independently. There's no standardized request abstraction layer. Adding a new provider requires duplicating the full request/retry/error-handling pattern. The `google` provider uses a different model name format than others, risking configuration errors.

### `recon/scraper/downloader.py` sends API key in Authorization header over HTTP (low)
- **Location:** `recon/scraper/downloader.py` (line 57)
- **Why:** The OpenAI transcription sends the API key over HTTPS (secure), but if there's ever a debug proxy or MITM, the API key is visible in the header. This is acceptable practice but worth noting for security-conscious deployments.

### The `skeleton_ripper` pipeline uses file system as job state (medium)
- **Locations:** `recon/skeleton_ripper/pipeline.py` (lines 366-401)
- **Why fragile:** Pipeline outputs are saved to timestamped directories (`data/recon/reports/{timestamp}_{job_id}/`). If the system clock is wrong, timestamps can collide. There's no cleanup mechanism — these reports accumulate forever in the filesystem.

### Flask app runs on fixed port 5001 (low)
- **Location:** `recon/web/app.py` (line 378)
- **Why fragile:** Port 5001 might be in use on some systems. There is no port fallback or PORT environment variable support. The `run-recon-ui.sh` script doesn't check for port availability.

## Improvement Opportunities

### Standardize on pyproject.toml with package metadata and tool config
- **What to do:** Create a `pyproject.toml` with project metadata, test runner config (`[tool.pytest.ini_options]`), linter config (`[tool.ruff]`), and an editable install path. This eliminates all `sys.path.insert` hacks.
- **Expected benefit:** Clean imports, standard test runner, consistent linting, and a single source of truth for project configuration.

### Add a proper test suite for `recon/` module
- **What to do:** Write unit tests for `recon/config.py` (credential loading, competitor loading), `recon/tracker.py` (state management, staleness checks), `recon/bridge.py` (topic generation), `scoring/engine.py` (scoring logic). Use mocking for external dependencies (instaloader, yt-dlp, OpenAI).
- **Expected benefit:** Confidence in refactoring, early detection of regressions, documented behavior.

### Centralize .env loading into a single utility module
- **What to do:** Move `load_env()` and `update_env()` from the individual scripts into a shared utility module (e.g., `scripts/lib/env_utils.py` or add to `recon/utils/`).
- **Expected benefit:** Eliminates code duplication, ensures consistent env loading behavior.

### Implement in-memory caching for `agent-brain.json`
- **What to do:** Use `functools.lru_cache` or a simple TTL-based cache for `load_brain_context()` and related functions in `recon/config.py`, `recon/bridge.py`, and `scoring/engine.py`.
- **Expected benefit:** Eliminates redundant file I/O on every request.

### Add schema validation
- **What to do:** Use Python's `jsonschema` library to validate data against the schemas in `schemas/`. Add validation at key write points (saving topics, saving skeletons, saving scripts).
- **Expected benefit:** Catches data format drift early. Makes schema files actually useful.

### Add active_jobs cleanup in the Flask web UI
- **What to do:** Set a max age or max size for `active_jobs`, or clean up completed jobs after a timeout.
- **Expected benefit:** Prevents memory leak in long-running UI sessions.

### Add port fallback and configuration to Flask UI
- **What to do:** Check port availability and fall back to next port. Support `PORT` environment variable. Remove `debug=True` by default.
- **Expected benefit:** More robust local server startup.

---

*Concerns audit: 2026-07-09*