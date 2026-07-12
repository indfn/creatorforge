---
phase: 02-security-hardening
reviewed: 2026-07-12T12:00:00Z
depth: standard
files_reviewed: 7
files_reviewed_list:
  - production/AudioGeneration/tts_generation.py
  - agent_core/recon/web/app.py
  - agent_core/recon/bridge.py
  - agent_core/scoring/rescore.py
  - agent_core/recon/config.py
  - agent_core/recon/scraper/downloader.py
  - pyproject.toml
findings:
  critical: 1
  warning: 3
  info: 6
  total: 10
status: issues_found
---

# Phase 02: Code Review Report — Security Hardening & Packaging

**Reviewed:** 2026-07-12T12:00:00Z
**Depth:** standard
**Files Reviewed:** 7
**Status:** issues_found

## Summary

Reviewed 7 source files modified as part of Phase 2 (Security Hardening & Packaging). The review assessed each file against the six security concerns (SEC-01 through SEC-07) as well as general code quality.

**What's done well:**
- Env var usage (SEC-01) is comprehensive, with proper fallback chains and validation
- Flask host binding defaults to 127.0.0.1 and debug defaults to False (SEC-02) — secure defaults
- Fernet encryption (SEC-03) has correct key generation, file permissions (0o600), and decryption error handling
- Settings whitelist (SEC-04) is implemented as a `frozenset` with URL and provider validation
- No `sys.path.insert` hacks remain in `agent_core/` (SEC-06) — imports resolve through the package structure
- No dead functions were found in the reviewed files (SEC-07)
- pyproject.toml entry points and package discovery look correct (SEC-05)

**Key concerns:**
1. **Critical:** `agent_core/scoring/rescore.py:15` — `PROJECT_ROOT` path resolution is off by one parent directory, causing `data/topics/` lookups to fail
2. `bridge.py:51` — `weights` parameter accepted but never consumed (dead parameter)
3. `config.py:63` — Broad `except` catches `KeyboardInterrupt`/`SystemExit`
4. `app.py:216-222` — Fragile `test_request_context()` pattern used inside a live request

## Critical Issues

### CR-01: Wrong PROJECT_ROOT path in rescore.py breaks data directory resolution

**File:** `agent_core/scoring/rescore.py:15`
**Issue:** `PROJECT_ROOT = Path(__file__).parent.parent` resolves to `agent_core/` instead of the project root directory. The file lives at `agent_core/scoring/rescore.py`, so `parent.parent` = `agent_core/`. This means `find_latest_topics_file()` (line 22) looks for `agent_core/data/topics/` which doesn't exist, and CLI resolution (line 125) resolves relative paths incorrectly.

Compare with the correct pattern in `agent_core/recon/config.py:17-18`:
```python
PIPELINE_DIR = Path(__file__).parent.parent.parent  # 3 levels: recon -> agent_core -> root
DATA_DIR = PIPELINE_DIR / "data"
```

**Fix:** Change line 15 from:
```python
PROJECT_ROOT = Path(__file__).parent.parent
```
to:
```python
PROJECT_ROOT = Path(__file__).parent.parent.parent
```

This aligns with the same convention used by `config.py` and `bridge.py`.

## Warnings

### WR-01: `weights` parameter passed but never consumed in `skeleton_to_topic()`

**File:** `agent_core/recon/bridge.py:51`
**Issue:** The `skeleton_to_topic()` function accepts a `weights: Dict[str, float]` parameter, and callers pass `weights=weights` at line 180. However, the parameter is never referenced in the function body — scoring is delegated entirely to `engine_score_topic()` (lines 78-84), which has its own weight-handling logic. This is either a dead parameter from an earlier design or indicates a gap where learning weights should influence competitor topic scoring but don't.

**Fix:** Either:
1. Remove the unused `weights` parameter from the function signature and all call sites, or
2. Propagate weights into the scoring call if they are meant to influence the scoring engine. If the intent is to override or augment the scoring engine's internal weights, add the logic; otherwise remove the dead parameter.

### WR-02: Broad `except` catches `KeyboardInterrupt` and `SystemExit`

**File:** `agent_core/recon/config.py:63`
**Issue:** `except (InvalidToken, Exception):` — Since `InvalidToken` is a subclass of `Exception`, listing it separately is redundant. More importantly, bare `Exception` catches `KeyboardInterrupt` and `SystemExit`, which should generally propagate. For a credentials decryption function, this means a user hitting Ctrl+C during decryption would be silently swallowed and `None` returned instead of the process exiting.

**Fix:** Change to:
```python
except Exception:
    return None
```

`InvalidToken` is already covered by `Exception`, and `KeyboardInterrupt`/`SystemExit` will propagate correctly.

### WR-03: `app.test_request_context()` used inside live request for internal routing

**File:** `agent_core/recon/web/app.py:216-222`
**Issue:** The `api_scrape_all()` endpoint creates an `app.test_request_context()` inside a running Flask request to call `api_scrape_competitor()` as an internal sub-request. Test request contexts are designed for unit tests, not production request handling. In threaded WSGI servers (the default Flask dev server is threaded), the test context could conflict with the outer request context, leading to `RuntimeError: Working outside of request context` or context leaks.

**Fix:** Refactor the shared logic into a helper function that both `api_scrape_competitor` and `api_scrape_all` can call directly, avoiding sub-request routing:

```python
def _scrape_competitor(handle_clean: str, max_reels: int = 50) -> str:
    """Internal: start a scrape job and return job_id."""
    config = load_config()
    competitor = next((c for c in config.competitors if c.handle.lstrip("@") == handle_clean), None)
    if not competitor:
        raise ValueError(f"Competitor @{handle_clean} not found")
    # ... job creation and threading logic ...
    return job_id

# Then in api_scrape_all:
for c in competitors:
    try:
        job_id = _scrape_competitor(c.handle.lstrip("@"))
        job_ids.append(job_id)
    except ValueError:
        continue
```

## Info

### IN-01: `python-dotenv` listed as dependency but not imported

**File:** `pyproject.toml:18`
**Issue:** `python-dotenv>=1.0.0` is listed in dependencies, but none of the reviewed source files import or use `dotenv`. The project implements a custom `.env` parser in `config.py:_load_env_file()` (lines 69-91) instead. If `python-dotenv` is not used anywhere else in the project, this dependency should be removed to keep the dependency tree lean.

**Fix:** Verify whether `python-dotenv` is used elsewhere in the codebase. If not, remove it from `pyproject.toml`. If the intent is to migrate from the custom parser to `python-dotenv`, this is acceptable but should be noted in the plan.

### IN-02: `app.secret_key` regenerated on every restart

**File:** `agent_core/recon/web/app.py:45`
**Issue:** `app.secret_key = os.urandom(24)` generates a new random key on every application startup. This invalidates all existing Flask session cookies (signed cookies become unverifiable). For a local development dashboard this is acceptable but could cause confusing session-drop behavior during restarts.

**Fix:** Read `secret_key` from an environment variable with `os.urandom(24)` as fallback:
```python
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or os.urandom(24).hex()
```

### IN-03: API key loaded at module level in TTS CLI

**File:** `production/AudioGeneration/tts_generation.py:12`
**Issue:** `API_KEY = os.environ.get("GEMINI_API_KEY", "")` is evaluated at import time rather than inside `main()`. If the module is imported (not just run as `__main__`), the environment variable is read once at import. Changes to the environment after import won't be reflected. For a CLI tool primarily used via `__main__`, this is a minor concern.

**Fix:** Move the env var read inside `main()` (post-argparse) for consistency:
```python
def main():
    args = parser.parse_args()
    api_key = os.environ.get("GEMINI_API_KEY", "")
    ...
```

### IN-04: Legacy plaintext credentials fallback opens latent attack surface

**File:** `agent_core/recon/config.py:152-164`
**Issue:** When Fernet decryption of `.credentials` fails, the code falls back to parsing the file as legacy plaintext `key=value` lines. This means an attacker who can write to the `.credentials` file can bypass encryption entirely by corrupting the Fernet data (causing decryption to fail) and providing plaintext credentials. The file permission (`0o600`) mitigates this, but the fallback lowers the security baseline.

**Fix:** Consider removing the legacy plaintext fallback after a migration grace period, since encrypted `.credentials` files are now the standard:
```python
if CREDENTIALS_FILE.exists():
    raw = CREDENTIALS_FILE.read_bytes()
    decrypted = _decrypt_credentials(raw)
    if decrypted is None and not _is_legacy_format(raw):
        logger.warning("CONFIG", "Failed to decrypt credentials file")
    elif decrypted is not None:
        creds.update(decrypted)
    # Gradually phase out legacy branch
```

### IN-05: `_extract_views()` doesn't handle million-scale (`M`) view counts

**File:** `agent_core/scoring/rescore.py:105-116`
**Issue:** The `_extract_views()` regex handles comma-delimited integers (e.g., `504,167 views`) and `K` suffix (e.g., `100K views`) but not `M` suffix (e.g., `2.5M views` or `1M views`). Viral content exceeding 1M views would be scored as 0 views, losing the competitor bonus.

**Fix:** Add `M`-suffix handling:
```python
match = re.search(r"([\d.]+)M\s*views", engagement_str, re.IGNORECASE)
if match:
    return int(float(match.group(1)) * 1000000)
```

### IN-06: Reviewed file path discrepancy for rescore.py

**File:** (review list discrepancy)
**Issue:** The `files_to_read` list specified `agent_core/recon/scoring/rescore.py`, which does not exist — no `scoring/` subdirectory exists under `agent_core/recon/`. The actual file is at `agent_core/scoring/rescore.py` (under the root `scoring` package, not `recon/scoring`). The import inside `bridge.py` correctly references `agent_core.scoring.engine` (line 15), confirming the correct path. The file list should be updated for consistency.

**Fix:** Update the file reference to `agent_core/scoring/rescore.py`.

---

_Reviewed: 2026-07-12T12:00:00Z_
_Reviewer: gsd-code-reviewer_
_Depth: standard_
