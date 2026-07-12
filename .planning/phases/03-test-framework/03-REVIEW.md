---
phase: 03-test-framework
reviewed: 2026-07-12T12:00:00Z
depth: standard
files_reviewed: 12
files_reviewed_list:
  - tests/conftest.py
  - tests/test_scoring/test_engine.py
  - tests/test_recon/test_config.py
  - tests/test_recon/test_bridge.py
  - tests/test_recon/storage/test_models.py
  - tests/test_recon/skeleton_ripper/test_pipeline.py
  - pyproject.toml
  - tests/__init__.py
  - tests/test_scoring/__init__.py
  - tests/test_recon/__init__.py
  - tests/test_recon/storage/__init__.py
  - tests/test_recon/skeleton_ripper/__init__.py
findings:
  critical: 0
  warning: 4
  info: 5
  total: 9
status: issues_found
---

# Phase 03: Code Review Report

**Reviewed:** 2026-07-12T12:00:00Z
**Depth:** standard
**Files Reviewed:** 12
**Status:** issues_found

## Summary

Reviewed the test framework across 12 files (6 test modules, 1 conftest, 1 pyproject.toml, 4 `__init__.py` files). Overall test quality is solid — fixtures are well-isolated with `tmp_path` + `monkeypatch`, mocking paths are correct, and coverage is comprehensive across all 6 areas (config, scoring, bridge, pipeline, storage, pytest setup). No critical security or correctness bugs found.

Key issues: one test relies on a weak assertion that masks potential env-var leakage, a module-level `sys.modules` mock imposes a global side-effect, a skipped test contains orphaned live code, and a scoring test comment is misleading. Several info-level improvements are also noted.

## Warnings

### WR-01: Weak assertion in `test_cascade_empty` masks potential env-var leakage

**File:** `tests/test_recon/test_config.py:360-371`
**Issue:** `test_cascade_empty` only asserts `isinstance(result, dict)`, which is trivially true. The test does NOT clean environment variables before calling `load_credentials()`. If the developer's shell has `IG_USERNAME`, `LLM_API_KEY`, or any env var defined in the `env_map` (lines 169-181 of `config.py`), those values will leak into the test result. The test would pass regardless, silently hiding the leakage.

```python
def test_cascade_empty(self, monkeypatch, tmp_path):
    self._setup_encryption(monkeypatch, tmp_path)
    monkeypatch.setattr(config, "CREDENTIALS_FILE", tmp_path / ".credentials")
    monkeypatch.setattr(config, "ENV_FILE", tmp_path / ".env")
    # No files, no env vars beyond CREDENTIALS_ENCRYPTION_KEY

    result = config.load_credentials()
    assert isinstance(result, dict)  # ← Always passes, even with leaked env vars
```

**Fix:** Either (a) assert the result is actually empty, or (b) monkeypatch.delenv all known credential env vars before calling `load_credentials()`:

```python
def test_cascade_empty(self, monkeypatch, tmp_path):
    self._setup_encryption(monkeypatch, tmp_path)
    monkeypatch.setattr(config, "CREDENTIALS_FILE", tmp_path / ".credentials")
    monkeypatch.setattr(config, "ENV_FILE", tmp_path / ".env")
    # Clean all credential env vars to prevent leakage
    for env_var in ["IG_USERNAME", "IG_PASSWORD", "LLM_API_KEY",
                    "TRANSCRIBE_API_KEY", "OPENAI_API_KEY", "LLM_BASE_URL",
                    "LLM_MODEL", "TRANSCRIBE_BASE_URL", "TRANSCRIBE_MODEL",
                    "TRANSCRIBE_PROVIDER", "WHISPER_MODEL"]:
        monkeypatch.delenv(env_var, raising=False)

    result = config.load_credentials()
    assert result == {}  # Enforce isolation
```

### WR-02: Module-level `sys.modules` mock is a persistent global side-effect

**File:** `tests/test_recon/skeleton_ripper/test_pipeline.py:17-18`
**Issue:** `sys.modules["instaloader"] = MagicMock()` runs at module import time (i.e., when pytest collects this file). The mock persists in `sys.modules` for the entire pytest run. If any other test module ever imports `instaloader` (directly or transitively), it will receive the MagicMock instead of the real module.

```python
# Must be done before any pipeline imports to prevent instaloader ImportError
sys.modules["instaloader"] = MagicMock()
```

**Fix:** Move this into a conftest fixture with `autouse=True` at the session level, or use a `unittest.mock.patch.dict` context to scope the mock:

```python
@pytest.fixture(autouse=True, scope="session")
def mock_instaloader():
    """Mock instaloader globally to prevent ImportError when pipeline module is loaded."""
    with patch.dict("sys.modules", {"instaloader": MagicMock()}):
        yield
```

### WR-03: Skipped test with active (dead) test body

**File:** `tests/test_recon/skeleton_ripper/test_pipeline.py:537-571`
**Issue:** `test_partial_creator_failure` is decorated with `@pytest.mark.skip` but contains a full, non-trivial test body (~20 lines of code). This code is never executed. The test covers an important multi-creator scenario (one creator fails, another succeeds). It should either be un-skipped (if functional) or the body should be removed to avoid misleading readers.

```python
@pytest.mark.skip(reason="Complex error simulation — see test for multi-creator scenario")
def test_partial_creator_failure(self, pipeline_mocks, tmp_path, monkeypatch):
    # ... 20 lines of test code never executed ...
```

**Fix:** If the test is valid and passes, remove the skip decorator. If the scenario cannot be cleanly tested yet, replace the body with a single assertion documenting the gap:

```python
@pytest.mark.skip(reason="Multi-creator partial failure not fully tested. "
                         "See test_partial_creator_failure for the untested scenario.")
def test_partial_creator_failure(self):
    """When one creator has no reels, pipeline continues with others.
    Currently not tested due to complexities with mock sequencing."""
    pass
```

### WR-04: Misleading comment about pain-point bonus logic

**File:** `tests/test_scoring/test_engine.py:141-152`
**Issue:** The inline comment says "Single pain point with 4 stem hits → only 1 point matched (< 2) → no bonus". This is misleading: the `>= 2` threshold refers to the **number of distinct pain points** matched (not stem hits). The code at `engine.py:170` checks `_count_pain_point_matches(...) >= 2`. A single pain point with 100 stem hits still counts as "1 point matched". The comment should say "only 1 pain point matched out of 2 required" to be clear.

```python
# Single pain point with 4 stem hits → only 1 point matched (< 2) → no bonus
#                                                        ^^^^
# This reads like "stem hits < 2" but the code checks "pain points >= 2"
```

**Fix:**
```python
# Single pain point matched (4 stem hits) → only 1 pain point (need >= 2) → no bonus
```

---

## Info

### IN-01: `TestScoreTopic` tests have latent filesystem coupling

**File:** `tests/test_scoring/test_engine.py:280-367`
**Issue:** Tests in `TestScoreTopic` call `engine.score_topic()` which internally calls `load_brain_context()` → reads the real `BRAIN_FILE` from disk (defined at `engine.py:13` as a path relative to `agent_core/scoring/engine.py`). If the real `agent-brain.json` exists with different data, the scoring results could differ from expected. While the current assertions (checking for keys, non-negativity, passthrough values) are resilient to varying brain data, the coupling to real filesystem is latent — a future test that asserts absolute scores would break.

**Fix:** Either mock `BRAIN_FILE` via monkeypatch (as `TestLoadBrainContext` already does) or mock `load_brain_context` to return a known fixture dict. The pattern in `TestScoreTopic` is acceptable for the current assertion set but should be documented and guarded against score-sensitive assertions.

### IN-02: `load_latest_skeletons` missing test for invalid JSON

**File:** `tests/test_recon/test_bridge.py:584-661`
**Issue:** `bridge.load_latest_skeletons()` reads `skeletons.json` and calls `json.load(f)` without error handling. If the file contains invalid JSON, an unhandled `json.JSONDecodeError` propagates. No test covers this edge case. All other file-reading functions in the codebase handle missing files gracefully; this one should at minimum have a test documenting the current behavior (even if that behavior is "raises").

### IN-03: Pipeline convenience function tests rely on `pipeline_mocks` fixture chain without explicit isolation

**File:** `tests/test_recon/skeleton_ripper/test_pipeline.py:798-810`
**Issue:** `test_run_skeleton_ripper_module_function` calls `run_skeleton_ripper()` which creates `SkeletonRipperPipeline()` without a `base_dir` argument, meaning it reads `RECON_DATA_DIR` from module globals. The fixture `pipeline_mocks` patches this global — if that fixture chain ever breaks (e.g., a future refactor changes how `RECON_DATA_DIR` is accessed), the test could silently write to the real filesystem. Adding an explicit `monkeypatch` for `RECON_DATA_DIR` within the test would provide defense-in-depth.

### IN-04: Missing test for `score_content_gap` with empty/edge text

**File:** `tests/test_scoring/test_engine.py:155-162`
**Issue:** The `CONTENT_GAP_CASES` parameter set doesn't include edge cases like empty text, very long text, or text with only stop-words. The `score_content_gap` function returns base score `6` for any text with no pillar keyword matches, but this fallback is not explicitly tested. Every other scoring function has been tested with edge cases.

### IN-05: `_match_pillars` "catch-all" logic may produce surprising behavior for mismatched pillars

**File:** `tests/test_recon/test_bridge.py:273-334`
**Issue:** The `_match_pillars` function falls back to the first pillar when no pillar name matches the text. This "catch-all" behavior means topics about "cooking recipes" get tagged as "AI Automation" if that's the first pillar. While tested in `test_no_match_returns_first_pillar` and `test_text_with_no_relevant_keywords_gets_catch_all`, this design choice has semantic implications that downstream code should be aware of. Consider testing explicitly that this fallback is intentional (e.g., by asserting that the first pillar is always present in the result).

---

## Detailed Analysis by Area

### TEST-01: pytest Configuration & Conftest Fixtures
- **pyproject.toml**: Correct `testpaths`, `python_files`, `pythonpath` config. Markers defined for `slow`, `integration`, `online`.
- **`conftest.py`**: All fixtures scoped `function`, use `tmp_path` + `monkeypatch`, no `autouse=True`. Good isolation discipline.
- All `__init__.py` files exist and are empty — correct for package discovery.
- `mock_agent_core_packages` fixture correctly patches the logger path (`agent_core.recon.utils.logger.get_logger`).
- `isolated_credentials` fixture correctly patches all config module paths.

### TEST-02: Scoring Engine Tests
- All 4 criteria tested with parameterized cases.
- Weighted total tests correct (equal, custom, missing key, zero weight, rounding).
- Competitor bonus tests include immutability check and cap-at-10.
- `load_brain_context` edge cases: missing file, valid file, missing sections, no competitors, handle stripping. Comprehensive.
- **WR-04** and **IN-01**, **IN-04** above.

### TEST-03: Skeleton Pipeline Tests
- All 5 stages covered via mocks.
- Error paths: no transcripts, no skeletons, missing credentials, login failure, no reels, empty usernames, download failure, transcribe failure.
- Cache integration: hit skips download/transcribe, miss calls both.
- Multi-creator tested.
- Mocking paths verified correct against source (`pipeline.py` imports verified as correct).
- **WR-02** and **WR-03** above.

### TEST-04: Bridge Tests
- Helper functions: `load_brain_pillars` (missing file, empty, missing name, missing key), `load_brain_learning_weights` (missing file, partial), `_generate_topic_title` (value source, hook fallback, creator fallback, truncation), `_match_pillars` (direct, no-match catch-all, empty, case-insensitive, multiple).
- `skeleton_to_topic`: all required keys, ID format, scoring keys, competitor flag, pillars, coverage, description formatting, status.
- `save_topics_jsonl`: path correctness, append, dedup, directory creation, JSON validity.
- `load_latest_skeletons`: most recent, no reports, skip dirs without skeletons, multiple skeletons.
- **IN-02** and **IN-05** above.

### TEST-05: Storage Tests
- CRUD: create (required fields, all fields), get (existing, nonexistent, to_dict), update (title, starred, metadata, unknown field ignored, no-change, composite), delete (delete, nonexistent, direct SQL).
- List: all, filter by type, by starred, limit/offset, collection_id, empty.
- FTS search: title, preview, multiple terms, limit, no match.
- Collection: create, list, to_dict.
- AssetCollection: add, remove, filter, duplicate idempotent, cascade delete.
- Edge cases: missing type raises, unknown field ignored, recreate after delete, metadata None, toggled starred.
- No cross-test state leakage — `db` fixture uses `tmp_path` + monkeypatched `DATABASE_PATH`.
- `init_db()` is safe to call multiple times (IF NOT EXISTS).

### TEST-06: Config Tests
- `_load_env_file`: key=value, comments/blanks, quoted values, inline comments, missing file, empty file, `=` in value.
- `_get_encryption_key`: env var priority, key file fallback, auto-generate with 0600 perms, stability.
- Encrypt/decrypt: roundtrip, binary output (plaintext not leaked), corrupted data returns None, wrong key returns None.
- `load_competitors`: missing file, partial entries, empty list, platform normalized.
- `load_credentials`: encrypted, plaintext fallback, env file overrides, env var overrides, cascade empty.
- `save_credentials`: encrypted blob, 0600 perms, roundtrip, empty, dir created.
- `load_config`: full assembly, defaults, LLM key fallback, transcribe fallback, individual overrides.
- Filtered competitors: IG/YT filters, empty when no match, missing brain file.
- **WR-01** above.

---

_Reviewed: 2026-07-12T12:00:00Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
