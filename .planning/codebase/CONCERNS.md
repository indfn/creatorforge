# Codebase Concerns

**Analysis Date:** 2026-07-10

## Tech Debt

### Stub Implementation Gap — Entire Publishing, Analytics, and Production Modules

- **Issue:** 15+ public functions across four modules are unimplemented stubs raising `NotImplementedError`. These represent the entire publishing pipeline and analytics feedback loop.
- **Files:**
  - `agent_core/publishing/uploader.py` — `upload_video()` (line 16)
  - `agent_core/publishing/oauth.py` — `get_authenticated_service()` (line 10), `refresh_token_if_expired()` (line 22)
  - `agent_core/publishing/scheduler.py` — `best_time()` (line 10), `schedule_for_peak()` (line 22)
  - `agent_core/publishing/metadata.py` — `generate_title()` (line 7), `generate_description()` (line 20), `generate_tags()` (line 33)
  - `agent_core/analytics/collector.py` — `collect_recent()` (line 7), `collect_for_video()` (line 20)
  - `agent_core/analytics/insights.py` — `aggregate_all()` (line 8), `aggregate_channel()` (line 17)
  - `agent_core/analytics/brain_updater.py` — `update_brain()` (line 8), `update_weights()` (line 20)
  - `production/VisualGeneration/asset_scraper.py` — `fetch_broll()` (line 7), `fetch_image()` (line 21)
  - `production/VisualGeneration/sfx_scraper.py` — `fetch_sfx()` (line 7)
  - `production/VisualGeneration/fallback_cli.py` — `generate_bar_chart()` (line 8), `generate_text_slide()` (line 22)
  - `production/AudioGeneration/force_align.py` — `align()` (line 10)
- **Impact:** The entire video upload, scheduling, SEO metadata generation, analytics collection, brain evolution loop, visual asset generation, and force alignment systems are non-functional. This constitutes ~70% of the intended feature surface.
- **Fix approach:** Implement each stub incrementally. Prioritize OAuth + uploader first (core path), then analytics collector, then the rest.

### `app.test_request_context()` Used in Production Route Handler

- **Issue:** `agent_core/recon/web/app.py` line 211 uses Flask's test request context (`app.test_request_context()`) inside the production `api_scrape_all()` route handler to invoke another route internally. This is a misuse of test infrastructure that creates hidden request context dependencies.
- **Files:** `agent_core/recon/web/app.py` (lines 211-221)
- **Impact:** Fragile internal dispatch — if `api_scrape_competitor` changes its request parsing behavior, `api_scrape_all` silently breaks. Also creates confusing context stack behavior.
- **Fix approach:** Extract the shared logic into a private helper function (`_scrape_competitor(handle, max_reels)`), call it directly from both routes instead of routing through Flask's WSGI context.

### Sys.path Manipulation in Multiple Modules

- **Issue:** Three files inject project root into `sys.path` at import time using `sys.path.insert(0, ...)`. This is fragile, bypasses proper Python packaging, and makes imports dependent on execution context.
- **Files:**
  - `agent_core/recon/bridge.py` (line 18)
  - `agent_core/recon/web/app.py` (line 19)
  - `agent_core/scoring/rescore.py` (line 17)
- **Impact:** Import resolution depends on how the script is invoked. Running `python3 path/to/file.py` from different directories produces different import behavior. Broke standard tooling (pylint, mypy, pytest).
- **Fix approach:** Install the project as a pip-installable package with `setup.py`/`pyproject.toml` and use `PYTHONPATH` consistently.

### Unused `weights` Parameter Passed Through

- **Issue:** `agent_core/recon/bridge.py` function `skeleton_to_topic()` accepts a `weights` parameter (line 55) but never uses it — only `pillars` is used. The parameter is threaded through `generate_topics_from_skeletons()` unnecessarily.
- **Files:** `agent_core/recon/bridge.py` (lines 55, 174)
- **Impact:** Misleading API surface. Future developers may think weights are applied in bridge when they're only used by the scoring engine internally.
- **Fix approach:** Remove the unused `weights` parameter from `skeleton_to_topic()` and `generate_topics_from_skeletons()`.

### Legacy `transcribe_video_openai` Wrapper

- **Issue:** `agent_core/recon/scraper/downloader.py` line 122 defines `transcribe_video_openai()` as a thin legacy wrapper around `transcribe_video()` with no additional logic. It exists only for backward compatibility but has no callers.
- **Files:** `agent_core/recon/scraper/downloader.py` (lines 122-124)
- **Impact:** Dead code that creates confusion about which transcription function to use.
- **Fix approach:** Remove the wrapper, update any hypothetical import references.

### Comment-Out-Based Optional Dependencies

- **Issue:** `requirements.txt` lists six optional dependencies as commented-out lines with installation instructions in comments. This means they don't get installed by default and developers must manually discover and uncomment them.
- **Files:** `requirements.txt` (lines 7-8, 22-24)
- **Impact:** Poor developer experience. Features like `instaloader`, `openai-whisper`, `faster-whisper`, `Pillow`, and `matplotlib` are silently disabled. Users encounter `ImportError` or `WHISPER_AVAILABLE = False` at runtime without clear guidance.
- **Fix approach:** Either make them required (add to requirements.txt), use optional extras groups (`pip install creatorforge[all]`), or auto-detect and log clear installation instructions at first use.

---

## Security Considerations

### Hardcoded API Key in Production Code

- **Risk:** `production/AudioGeneration/tts_generation.py` contains a hardcoded API key `API_KEY = "your-api-key-3"` at line 12. If committed (it is currently), this exposes credentials in the source repository.
- **Files:** `production/AudioGeneration/tts_generation.py` (line 12)
- **Current mitigation:** The value `"your-api-key-3"` appears to be a placeholder, but the code reads it as a live credential — `headers["x-goog-api-key"] = API_KEY` at line 121. If any developer replaces this with a real key, it will be committed to git.
- **Recommendations:** Move API key to environment variable (`GEMINI_API_KEY`) or `.env` file. The script should fail with a clear error if the environment variable is not set.
- **Priority:** High

### Hardcoded Proxy URL with Localhost Assumption

- **Risk:** `production/AudioGeneration/tts_generation.py` line 11 hardcodes `PROXY_URL = "http://127.0.0.1:8317/v1beta/models/gemini-3.1-flash-tts-preview:generateContent"`. This assumes a local proxy server is running on port 8317, and uses plain HTTP.
- **Files:** `production/AudioGeneration/tts_generation.py` (line 11)
- **Current mitigation:** None — the URL is hardcoded with no fallback or configuration option.
- **Recommendations:** Make the proxy URL configurable via environment variable with a sensible default. Document that the proxy must support HTTPS in production.

### Flask `debug=True` in Production Entry Point

- **Risk:** `agent_core/recon/web/app.py` line 381 runs `app.run(host='0.0.0.0', port=5001, debug=True)`. Flask's debug mode exposes the Werkzeug debugger and interactive debugger console, which allows arbitrary code execution if triggered. The host `0.0.0.0` means it binds to all network interfaces.
- **Files:** `agent_core/recon/web/app.py` (lines 381)
- **Current mitigation:** None — this is the only entry point for the Recon UI.
- **Recommendations:** Remove `debug=True` for production use. Add a `--debug` CLI flag or `FLASK_ENV=development` check. Restrict to `127.0.0.1` by default and add a `--host` flag.

### Plaintext Credential Storage

- **Risk:** `agent_core/recon/config.py` stores credentials in a plaintext `.credentials` file at `data/recon/.credentials` (line 17). This file is gitignored but stored unencrypted on disk with Instagram passwords, API keys, etc.
- **Files:** `agent_core/recon/config.py` (lines 140-146, the `save_credentials()` function)
- **Current mitigation:** The file is in `.gitignore` (line 14: `data/recon/`).
- **Recommendations:** Use the system keyring (`keyring` Python package) or at minimum encrypt the file with a derived key. The `.credentials` file should have restricted file permissions (`0600`).

### Insecure Settings API — No Validation or Sanitization

- **Risk:** `agent_core/recon/web/app.py` `api_save_settings()` (line 348) accepts any key in the request body and saves it directly to the credentials file without validation, sanitization, or type checking.
- **Files:** `agent_core/recon/web/app.py` (lines 348-361)
- **Current mitigation:** The write path is to a file in `.gitignore`'d directory.
- **Recommendations:** Whitelist allowed setting keys. Validate values before saving (e.g., URL format for base URLs, non-empty for API keys). Log all credential changes for auditability.

### OAuth Token Stored in Home Directory Plaintext

- **Risk:** YouTube OAuth token is stored at `~/.creatorforge/yt-token.json` (plaintext JSON) containing `token`, `refresh_token`, `client_secret`, etc.
- **Files:** `scripts/setup-yt-oauth.py` (line 35, 57-67), `scripts/fetch-yt-analytics.py` (line 38)
- **Current mitigation:** The `.creatorforge` directory is in `.gitignore` (line 73).
- **Recommendations:** Restrict file permissions to `0600` after writing. Consider using the system keyring for OAuth token storage.

---

## Performance Bottlenecks

### No Database Connection Pooling — Connection Per Query

- **Problem:** `agent_core/recon/storage/database.py` and `models.py` open a new SQLite connection for every query. The `get_db_connection()` function (line 85) is called in `Asset.get()`, `Asset.list()`, `Asset.search()`, `Collection.list()`, and all transaction operations. Each call creates a new connection with no reuse.
- **Files:** `agent_core/recon/storage/database.py`, `agent_core/recon/storage/models.py`
- **Cause:** No connection pooling or persistent connection pattern. Every CRUD operation opens, queries, and closes a connection.
- **Improvement path:** Use a connection pool (e.g., `sqlite3` connection cached per-thread) or use the `db_transaction()` context manager consistently. SQLite performs best with a single persistent connection per thread.

### Full Transcript Cache Iteration on Every Pipeline Run

- **Problem:** `SkeletonRipperPipeline._scrape_and_transcribe()` iterates through all cached transcript files using `list(self.cache.cache_dir.glob(...))` to check for cached content. With hundreds of cached files, this becomes a filesystem bottleneck.
- **Files:** `agent_core/recon/skeleton_ripper/pipeline.py` (lines 344-361)
- **Cause:** Cache lookup uses filesystem glob pattern matching instead of an index.
- **Improvement path:** Maintain a lightweight index (e.g., JSON map of platform/username/video_id → cache path) in memory, rebuilt only on startup.

### Large JSON Payloads in LLM Prompts

- **Problem:** `agent_core/recon/skeleton_ripper/synthesizer.py` passes the full `skeletons_json` (potentially hundreds of KB of JSON) into the LLM prompt via `json.dumps(skeletons, indent=2)`. This is sent to the LLM's chat completion API and billed per-token.
- **Files:** `agent_core/recon/skeleton_ripper/prompts.py` (line 177)
- **Cause:** No summarization or truncation before injecting skeleton data into prompts.
- **Improvement path:** Summarize skeleton data (aggregated stats, top patterns, compressed format) before passing to the LLM to reduce token consumption and cost.

### Sequential Per-Competitor Scraping

- **Problem:** `SkeletonRipperPipeline._scrape_and_transcribe()` processes competitors sequentially (line 234: `for idx, username in enumerate(config.usernames)`). For multi-competitor runs, each competitor's reels are scraped, downloaded, transcribed, and cached one at a time.
- **Files:** `agent_core/recon/skeleton_ripper/pipeline.py` (lines 234-341)
- **Cause:** No parallelization strategy for multiple competitors.
- **Improvement path:** Use `concurrent.futures.ThreadPoolExecutor` to scrape and transcribe competitors in parallel. The Instagram API rate limits (line 169: sleep 1s per 12 reels) make this particularly beneficial.

---

## Fragile Areas

### In-Memory Job Tracking with No Persistence

- **Files:** `agent_core/recon/web/app.py` (lines 53: `active_jobs = {}`)
- **Why fragile:** The `active_jobs` dictionary lives only in the Flask process memory. If the server restarts (deploy, crash, or `--reload` with debug=True), all running and completed job state is lost. There's no upper bound — long-running sessions accumulate jobs unboundedly.
- **Safe modification:** Add a cap on active jobs (e.g., `active_jobs = OrderedDict(maxlen=100)`). Persist completed job state to the existing SQLite database. Use a background cleanup thread for stale entries.
- **Test coverage:** None — no tests exist for any route handler.

### File-Based State With No Locking

- **Files:** `agent_core/recon/tracker.py` (lines 18-36)
- **Why fragile:** `filter_new_content()` reads, modifies, and saves state (line 35) but the caller is responsible for saving. If `save_state()` is not called, state mutations are lost. Multiple concurrent requests could cause interleaved read/write races. The `get_stale_competitors()` function reads state without any synchronization.
- **Safe modification:** Use `atomicwrites` or write to a temp file + rename pattern. Add a file-level lock (`fcntl.flock` or `portalocker`). Make state saving automatic in `filter_new_content()`.
- **Test coverage:** None.

### File System State Manager — No Cleanup or Bounds

- **Files:** `agent_core/recon/utils/state_manager.py` (lines 27-57)
- **Why fragile:** `save_job_state()` writes a new JSON file per job with no cleanup. Over many runs, the state directory accumulates unbounded files. `list_jobs()` reads all `.json` files in the directory — on every call.
- **Safe modification:** Add a TTL-based cleanup in the StateManager constructor. Cache the list of recent jobs in memory. Use the SQLite database instead of files for job state.
- **Test coverage:** None.

### Unbounded Logger Error Registry

- **Files:** `agent_core/recon/utils/logger.py` (line 56: `self.error_registry: Dict[str, Dict[str, Any]] = {}`)
- **Why fragile:** `error()` and `critical()` methods append error entries to `self.error_registry` dict with no upper bound. Over a long-running session, this grows unboundedly in memory. The singleton pattern means it persists across requests.
- **Safe modification:** Implement a ring buffer (max 1000 entries) or LRU cache for the error registry. Persist errors to the database or log file instead of holding them all in memory.

### Batch Extraction Binary Search Fallback on Parse Failure

- **Files:** `agent_core/recon/skeleton_ripper/extractor.py` (lines 102-118)
- **Why fragile:** When JSON parsing fails for a batch, the `_handle_parse_failure` method recursively halves the batch and retries. This binary search approach doubles the number of LLM API calls on failure. Worse, a single problematic transcript in a batch of 4 can trigger 2-3 additional API calls. There's no early abort for malformed LLM responses.
- **Safe modification:** Validate LLM response structure before attempting JSON parse. Add a cap on total retry cost. Consider extracting individually (sequential) instead of binary search when a batch fails.

### Thread Safety of Logger Singleton

- **Files:** `agent_core/recon/utils/logger.py` (lines 34-39)
- **Why fragile:** The `ReconLogger` uses double-checked locking for singleton creation (line 31-39), but the `__init__` method is not fully guarded by the lock after instance creation. If two threads race on first access, both can enter `__init__`, though the `_initialized` flag (line 42) prevents re-initialization. File writes are locked with `self._file_lock` (line 123).
- **Safe modification:** Use a module-level `_logger` initialization at import time (already partially done at line 189) instead of the class-level singleton pattern. Remove the singleton entirely and use the module-level instance.

---

## Scaling Limits

### SQLite Concurrency

- **Current capacity:** Single-writer, single-file SQLite database at `data/recon/recon.db`.
- **Limit:** SQLite serializes all write operations. With the Flask UI + background scrapers + scheduled tasks all writing to the same database, write contention will become a bottleneck at modest scale.
- **Scaling path:** Move to PostgreSQL for production. The application's data model (assets, collections) is simple and would map cleanly. For the immediate term, enable WAL mode: `PRAGMA journal_mode=WAL`.

### Flat File Cache

- **Current capacity:** All transcript caches stored as individual `.txt` files in a single `data/recon/cache/` directory.
- **Limit:** With thousands of files, filesystem operations (glob, stat) become slow. Some filesystems degrade beyond ~10K files per directory.
- **Scaling path:** Use a SQLite database as the cache backend with indexed lookups by (platform, username, video_id). This also enables TTL-based cache eviction and size limits.

---

## Test Coverage Gaps

### Entire Core Application Untested

- **What's not tested:** Zero test files exist anywhere in `agent_core/`, `production/`, or `scripts/`. No tests for: scoring engine, skeleton ripper pipeline, Instagram client, YouTube scraper, transcription, bridge, database models, config loading, Flask routes, or any utility module.
- **Files:** All files in `agent_core/`, `production/`, `scripts/`
- **Risk:** Every change to the scoring engine or pipeline is untested. Regression from editing LLM prompts or extraction logic cannot be caught. The Flask UI routes have no request/response validation tests.
- **Priority:** High

### No Integration Tests for External APIs

- **What's not tested:** Instagram (instaloader), YouTube (yt-dlp), OpenAI (transcription, LLM), Pexels/Flickr (asset scraping) integrations have no integration tests.
- **Files:** `agent_core/recon/scraper/instagram.py`, `youtube.py`, `downloader.py`, `llm_client.py`
- **Risk:** API contract changes by third-party providers will not be caught until runtime. The instaloader library breaking changes, YouTube API deprecations, or OpenAI endpoint changes will silently break the pipeline.
- **Priority:** Medium

### Scoring Engine Logic Untested

- **What's not tested:** All scoring heuristics — ICP relevance tiers, content gap calculation, proof potential detection, competitor bonuses, weighted total calculation.
- **Files:** `agent_core/scoring/engine.py` (all 292 lines), `scoring/rescore.py` (all 132 lines)
- **Risk:** The scoring engine drives topic prioritization. Incorrect scoring leads to bad content decisions. Edge cases like empty brain context, zero views, or malformed engagement strings are not validated.
- **Priority:** High

---

## Known Bugs

### Cached Transcript Parsing Ambiguity

- **Symptoms:** `SkeletonRipperPipeline._get_cached_transcripts()` (line 346) parses video_id from cached filename by splitting on `_` and taking the last part. Filenames follow the pattern `{platform}_{username}_{video_id}.txt`. If the video_id itself contains underscores (possible with some platform's IDs), the parsing produces an incorrect video_id.
- **Files:** `agent_core/recon/skeleton_ripper/pipeline.py` (lines 346-358)
- **Trigger:** Any video_id containing underscores.
- **Workaround:** Manually clear cache for affected videos. The pipeline still works — the video_id is cosmetic for the cached entry.

### Rescore Script View Count Extraction Fails on Certain Formats

- **Symptoms:** `_extract_views()` in `agent_core/recon/scoring/rescore.py` only handles "123,456 views" and "100K views" formats. Formats like "1.2M views", "123K Views" (capital V), or "123k views" (lowercase k) will silently return 0.
- **Files:** `agent_core/recon/scoring/rescore.py` (lines 107-118)
- **Trigger:** Engagement signals strings from topics with non-standard view formatting.
- **Workaround:** Manually fix the view string in the topics JSONL file before running rescore.

### `_match_pillars` Catch-All Fallback Creates False Positives

- **Symptoms:** `agent_core/recon/bridge.py` `_match_pillars()` (line 152-154) includes a fallback: if no pillar matches, it adds the first pillar as a catch-all. This means every topic gets assigned at least one pillar, even if it's completely unrelated.
- **Files:** `agent_core/recon/bridge.py` (lines 140-156)
- **Trigger:** Any topic whose text doesn't match any pillar keywords.
- **Workaround:** None. This is by-design behavior that introduces noise in pillar classification.

---

## Dependencies at Risk

### `instaloader` — Instagram API Scraping

- **Risk:** `instaloader` scrapes Instagram's public website, not an official API. It can break without notice when Instagram changes its DOM, login flow, or rate limiting. The library also requires the user's Instagram credentials (violates Instagram ToS for scraping).
- **Impact:** `agent_core/recon/scraper/instagram.py` becomes completely non-functional if Meta changes their graphql endpoint or login flow. Already affected by 2FA (line 86: "not supported in headless mode").
- **Migration plan:** Investigate Instagram Basic Display API or Meta Content Publishing API for authorized read access. For competitor research, no official alternative exists — this is inherently fragile.

### `yt-dlp` — YouTube Scraping

- **Risk:** `yt-dlp` is under active development but YouTube frequently breaks compatibility. The tool depends on reverse-engineering YouTube's internal APIs.
- **Impact:** `agent_core/recon/scraper/youtube.py` stops working when YouTube changes their data format or rate limiting. The `get_channel_videos()` function (line 26) parses `--dump-json` output which has changed format multiple times.
- **Migration plan:** Use YouTube Data API v3 for metadata (already partially set up in `scripts/fetch-yt-analytics.py`) and remove yt-dlp dependency for the metadata fetching path.

---

## Missing Critical Features

### No Force Alignment Implementation

- **Problem:** `production/AudioGeneration/force_align.py` is a stub. Word-level force alignment is required for hyperframe animation syncing (word-by-word caption highlighting). Without it, the render pipeline cannot produce synced captions.
- **Blocks:** Hyperframe caption animation, word-level timing for video render.

### No B-Roll or Asset Fetching Implementation

- **Problem:** `production/VisualGeneration/asset_scraper.py` and `sfx_scraper.py` are stubs. The entire visual asset pipeline (Pexels API, Flickr API, Pixabay, Freesound) is unimplemented.
- **Blocks:** Automated video production — no way to source footage, images, or sound effects programmatically.

### No YouTube Upload Implementation

- **Problem:** `agent_core/publishing/uploader.py` and `oauth.py` are stubs. The entire YouTube Data API v3 upload flow, OAuth token lifecycle management, and scheduling is unimplemented.
- **Blocks:** End-to-end content pipeline. Videos can be rendered but not published.

---

*Concerns audit: 2026-07-10*
