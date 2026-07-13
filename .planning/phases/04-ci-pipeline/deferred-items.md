# Deferred Items — Phase 04 CI Pipeline

## Missing instaloader dependency causes pipeline test failures

- **Found during:** Plan 04-02 verification (pytest run)
- **Issue:** `agent_core/recon/scraper/instagram.py` imports `instaloader` but it's not listed in `pyproject.toml` dependencies. This causes import-time failures in `tests/test_recon/skeleton_ripper/test_pipeline.py` (9 test failures, 18 errors).
- **Pre-existing:** Not introduced by Plan 04-02 changes (CI pipeline setup).
- **Action needed:** Add `instaloader` to `[project.dependencies]` or `[project.optional-dependencies]` in a future plan.
