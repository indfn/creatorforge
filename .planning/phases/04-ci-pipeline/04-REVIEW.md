---
phase: 04-ci-pipeline
reviewed: 2026-07-13T18:30:00Z
depth: standard
files_reviewed: 7
files_reviewed_list:
  - tests/test_schemas/conftest.py
  - tests/test_schemas/test_schema_valid.py
  - tests/test_schemas/test_schema_invalid.py
  - tests/test_scripts/test_fetch_yt_analytics.py
  - tests/test_scripts/test_fetch_ig_insights.py
  - .github/workflows/ci.yml
  - pyproject.toml
findings:
  critical: 0
  warning: 5
  info: 7
  total: 12
status: issues_found
---

# Phase 04: Code Review Report

**Reviewed:** 2026-07-13T18:30:00Z
**Depth:** standard
**Files Reviewed:** 7
**Status:** issues_found

## Summary

Reviewed test suites for JSON Schema validation (15 schemas), YouTube Analytics script, Instagram Insights script, CI pipeline configuration, and project tooling config. The test code is generally well-structured with comprehensive parametrization, clear fixtures, and good isolation through autouse monkeypatching. However, several warnings were found in the source scripts that the tests exercise: an unused parameter in the Instagram function, dead code in the YouTube script, and a fragile exception handling pattern. Coverage configuration excludes the scripts entirely, creating a blind spot for the analytics test suites. The CI pipeline is functional but lacks matrix testing and produces a coverage artifact of limited utility.

Imports from `scripts/` are correctly wired through `scripts/__init__.py` which uses `importlib` to register hyphen-named files (e.g., `fetch-yt-analytics.py`) as underscore-named modules (`scripts.fetch_yt_analytics`). All mock patch paths correctly target `scripts.fetch_yt_analytics.requests.get` and `scripts.fetch_ig_insights.requests.get`.

## Warnings

### WR-01: Unused `media_type` parameter in `get_media_insights`

**File:** `scripts/fetch-ig-insights.py:50`

**Issue:** The `media_type` parameter is accepted but never referenced in the function body. The function always reads `media_type` from the API response via `media.get("media_type")`. Call sites in `main()` (line 248) and tests pass this argument as if it controls behavior, but it has no effect. This creates misleading test semantics — e.g., `test_image_media_no_plays` passes `media_type="IMAGE"` but what actually controls the branch taken is the mock response's `media_type` field.

```python
# Parameter declared but never used:
def get_media_insights(media_id, access_token, media_type="VIDEO"):
    ...
    media = resp.json()
    # Function uses media.get("media_type"), NOT the parameter
    if media.get("media_type") in ("VIDEO", "REELS"):
        ...
    elif media.get("media_type") == "IMAGE":
        ...
```

**Fix:** Remove the parameter and update call sites. The `main()` function (line 248) passes `media.get("media_type")` as the third argument — since the function already fetches this from the API, the argument is redundant.

```python
def get_media_insights(media_id, access_token):
    """Fetch insights for a single media item."""
```

And update the call in `main()`:
```python
result = get_media_insights(media["id"], access_token)  # remove third arg
```

Update tests to stop passing the argument.

---

### WR-02: Dead code — `fetch_ctr` always returns `None` and is never called

**File:** `scripts/fetch-yt-analytics.py:183-214`

**Issue:** The `fetch_ctr` function has multiple issues:
1. Line 206 (`params["metrics"] = "views"`) overwrites the `cardClickRate` metric set on line 196, so the API call fetches `views` instead of CTR, but the return value (line 212) is always `None` regardless.
2. The function is never called by `main()` (line 269 sets `ctr = None` directly).
3. It has no test coverage.

This is 30 lines of dead code that creates maintenance burden and confusion.

```python
def fetch_ctr(video_id, published_at, oauth_token):
    ...
    params["metrics"] = "cardClickRate"   # line 196 — overwritten below
    ...
    params["metrics"] = "views"           # line 206 — overrides the above
    resp = requests.get(...)              # fetches views, not CTR
    return None                           # never returns anything else
```

**Fix:** Remove the entire `fetch_ctr` function. The note about CTR being unavailable via API is already handled in `main()` (lines 269-270). If the function is kept for future use, remove the unconditional `return None` and the dead code paths.

---

### WR-03: Overly broad exception handling with fragile `locals()` check in `get_oauth_token`

**File:** `scripts/fetch-yt-analytics.py:76-81`

**Issue:** The `except Exception` clause on line 76 catches all exceptions, including `AttributeError`, `TypeError`, or `ImportError` from the Google OAuth code on lines 58-74. The fallback on line 79 uses `locals()` to check whether `token_data` was assigned before the exception, then returns `token_data.get("token")` which itself could be `None` if the token key is missing. This pattern:
1. Masks real bugs in the OAuth initialization code
2. Uses `locals()` introspection instead of a controlled state variable
3. Returns `None` silently for several different failure modes

```python
try:
    token_data = json.loads(TOKEN_PATH.read_text())
    creds = Credentials(...)  # could raise TypeError, ImportError
    ...
except Exception as e:
    print(f"Warning: OAuth token refresh failed: {e}", file=sys.stderr)
    if "token_data" in locals() and token_data:  # fragile introspection
        return token_data.get("token")            # could also be None
    return None
```

**Fix:** Narrow the exception scope and use a controlled variable:

```python
def get_oauth_token():
    if not TOKEN_PATH.exists():
        return None
    try:
        token_data = json.loads(TOKEN_PATH.read_text())
    except (json.JSONDecodeError, OSError) as e:
        print(f"Warning: Could not read token file: {e}", file=sys.stderr)
        return None

    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        creds = Credentials(
            token=token_data["token"],
            refresh_token=token_data["refresh_token"],
            token_uri=token_data["token_uri"],
            client_id=token_data["client_id"],
            client_secret=token_data["client_secret"],
            scopes=token_data.get("scopes"),
        )
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token_data["token"] = creds.token
            TOKEN_PATH.write_text(json.dumps(token_data, indent=2))
        return creds.token
    except Exception as e:
        print(f"Warning: OAuth token refresh failed: {e}", file=sys.stderr)
        return token_data.get("token")  # safe — token_data is always defined here
```

---

### WR-04: Coverage configuration excludes `scripts/` from tracking

**File:** `pyproject.toml:50-57`

**Issue:** The `[tool.coverage.run]` section omits `*/scripts/*`, meaning `fetch-yt-analytics.py` and `fetch-ig-insights.py` have no coverage tracking despite having dedicated test suites in `tests/test_scripts/`. The CI runs `pytest --cov=agent_core` which only measures `agent_core/`, but the config-level omission means even if someone runs `pytest --cov=scripts`, the scripts would be excluded.

```toml
[tool.coverage.run]
source = ["agent_core"]
omit = [
    "*.venv/*",
    "*/tests/*",
    "*/production/*",
    "*/scripts/*",     # <- scripts excluded from coverage
    "*/setup.py",
]
```

**Fix:** Either remove `*/scripts/*` from the omit list and add `scripts` to the source list, or split into separate CI jobs for `agent_core` and `scripts` coverage. At minimum, remove the scripts exclusion so developers can opt in:

```toml
[tool.coverage.run]
source = ["agent_core", "scripts"]
omit = [
    "*.venv/*",
    "*/tests/*",
    "*/setup.py",
]
```

---

### WR-05: Missing timeout and connection error coverage in analytics tests

**File:** `tests/test_scripts/test_fetch_yt_analytics.py` and `tests/test_scripts/test_fetch_ig_insights.py`

**Issue:** Both test suites cover HTTP error scenarios (403, 500) but neither tests `requests.exceptions.Timeout` or `requests.exceptions.ConnectionError`. These are common failure modes for external API calls and should be covered to verify graceful degradation.

**Fix:** Add test cases in each class. For example, in `TestFetchAnalyticsApi`:

```python
def test_timeout_returns_empty(self, mock_response):
    from scripts.fetch_yt_analytics import fetch_analytics_api
    from requests.exceptions import Timeout

    with patch("scripts.fetch_yt_analytics.requests.get",
               side_effect=Timeout("Connection timed out")):
        result = fetch_analytics_api(
            "video_id", "2026-07-10T12:00:00Z", "test-token"
        )
    assert result == {}
```

Add similar tests for `fetch_data_api` (should propagate) and `get_media_insights` (should not crash).

---

## Info

### IN-01: Uneven schema invalid test coverage

**File:** `tests/test_schemas/test_schema_invalid.py`

**Issue:** Several schemas have minimal negative coverage:
- `production-order.schema.json`, `hyperframe.schema.json`, `swipe-hook.schema.json`, `insight.schema.json` — only 1 test each (missing all required fields)
- No wrong-type, bound violation, or `additionalProperties` tests for these schemas

Meanwhile, `hook.schema.json` and `angle.schema.json` have 4+ tests each covering multiple constraint types.

**Fix:** Add at least one type-violation test and one additionalProperties test for each schema that defines those constraints.

---

### IN-02: Duration parsing missing day-level ISO 8601

**File:** `tests/test_scripts/test_fetch_yt_analytics.py:50-60`

**Issue:** The parametrized `test_parse_iso8601_duration` covers hours, minutes, seconds, and empty/invalid strings, but has no test case with days (e.g., `P1DT2H30M`). The regex on line 86 of the source (`r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?"`) does not handle the `P{n}D` prefix at all, so `P1DT2H30M` would return 0 (unmatched → fallthrough). If the system ever processes videos longer than 24 hours, this would misparse silently.

**Fix:** Add a test with days and decide whether to support them:
```python
("P1DT2H30M", 0),  # Document that days are not supported (current behavior)
# OR update regex and test expected value
```

---

### IN-03: No CAROUSEL_ALBUM media type test

**File:** `tests/test_scripts/test_fetch_ig_insights.py`

**Issue:** Instagram's Graph API returns `media_type` values of `VIDEO`, `IMAGE`, and `CAROUSEL_ALBUM`. Only the first two are tested. The function's `if media.get("media_type") in ("VIDEO", "REELS")` path would miss `CAROUSEL_ALBUM`, meaning carousel posts get no insights metrics (fall through both VIDEO and IMAGE branches without error), which may be unexpected.

**Fix:** Add a test with `media_type="CAROUSEL_ALBUM"` to document expected behavior.

---

### IN-04: Coverage artifact uploads raw `.coverage` file only

**File:** `.github/workflows/ci.yml:37-43`

**Issue:** The CI uploads `.coverage` (a binary SQLite database from coverage.py) as an artifact. This file requires post-processing with `coverage xml` or `coverage html` to be human-readable. Consider generating both formats for immediate use in PR comments or browser viewing.

**Fix:**
```yaml
- name: Generate coverage reports
  run: |
    coverage xml -o coverage.xml
    coverage html -d coverage_html

- name: Upload coverage reports
  if: always()
  uses: actions/upload-artifact@v4
  with:
    name: coverage-report
    path: |
      .coverage
      coverage.xml
      coverage_html/
    retention-days: 7
```

---

### IN-05: No CI matrix strategy for Python versions

**File:** `.github/workflows/ci.yml:10-20`

**Issue:** The CI only tests on Python 3.11, but `pyproject.toml` specifies `requires-python = ">=3.10"`. Version-specific regressions (e.g., dict ordering changes, deprecated API removals) won't be caught.

**Fix:** Add a matrix strategy:
```yaml
jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: pip
          cache-dependency-path: pyproject.toml
```

---

### IN-06: B904 (raise-without-from) suppressed in Ruff config

**File:** `pyproject.toml:77`

**Issue:** The ruff rule `B904` (raise-without-from-inside-except) is ignored. This rule flags cases where an `except` block raises a new exception without chaining it via `from` — which can obscure the original exception context during debugging.

The `fetch-yt-analytics.py` script has several places where this pattern could apply (e.g., lines 31-33 catching `ImportError` and calling `sys.exit(1)`). While the explicit `raise` isn't used there, the blanket suppression should be scoped more carefully.

**Fix:** Replace the blanket ignore with per-file-ignores or remove it and fix any violations:
```toml
[tool.ruff.lint]
ignore = [
    "E501",
]
```

---

### IN-07: Duplicated insight metric parsing logic

**File:** `scripts/fetch-ig-insights.py:79-141`

**Issue:** The VIDEO/REELS branch (lines 79-114) and IMAGE branch (lines 116-141) share near-identical code for iterating over `insights_data`, extracting metric names and values, and assigning them to `result["metrics"]`. The only differences are the `metric` parameter string and the set of mapped names.

**Fix:** Extract a shared helper:
```python
def _parse_insights_metrics(insights_data, result):
    for item in insights_data:
        name = item["name"]
        value = item["values"][0]["value"] if item.get("values") else None
        if name == "reach":
            result["metrics"]["reach"] = value
        elif name == "saved":
            result["metrics"]["saves"] = value
        elif name == "shares":
            result["metrics"]["shares"] = value
        elif name == "plays":
            result["metrics"]["views"] = value
        elif name == "total_interactions":
            result["metrics"]["total_interactions"] = value
```

This is a code quality suggestion — not urgent, but reduces duplication and the risk of the two branches diverging.

---

## Files Without Issues

The following files were reviewed and found to have no bugs or correctness issues:

- `tests/test_schemas/conftest.py` — Clean fixture architecture. The `SCHEMA_DIR` path resolution, session-scoped `all_schemas` loader with count assertion, and wrapper-based `validator_for` fixture are well-designed. Note: the `all_schemas` assertion (`len(schemas) == 15`) is a useful canary when schemas are added/removed.
- `tests/test_schemas/test_schema_valid.py` — All 15 schemas have a minimal valid data case. The parametrization with descriptive IDs makes failures easy to diagnose.
- `tests/test_schemas/test_schema_invalid.py` — Strong coverage of missing required, wrong types, enum violations, `additionalProperties`, pattern/format, bounds, and minItems constraints. The `ids=[c[2][:50] ...]` truncation prevents overly long test IDs.
- `.github/workflows/ci.yml` — Correct GitHub Actions syntax, appropriate checkout/setup-python versions (`@v4`/`@v5`), pip caching, ruff/mypy/pytest integration. No syntax or logic errors.

---

_Reviewed: 2026-07-13T18:30:00Z_
_Reviewer: gsd-code-reviewer_
_Depth: standard_
