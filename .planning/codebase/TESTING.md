# Testing

**Analysis Date:** 2026-07-09

## Test Framework

**Runner/Assertions:** `unittest` (Python standard library) — all tests use `unittest.TestCase` subclasses

**No external test dependencies:** No pytest, no pytest plugins, no test-specific packages in `requirements.txt`

**Run Commands:**
```bash
python3 -m unittest discover skills/last30days/tests      # Run all tests
python3 -m unittest skills/last30days/tests/test_score.py  # Run single test file
python3 -m unittest skills/last30days/tests/test_score.py -k TestScoreRedditItems  # Run single test class
```

**Test files:** 8 test files, all under `skills/last30days/tests/`:
- `test_normalize.py` (138 lines)
- `test_score.py` (168 lines)
- `test_models.py` (135 lines)
- `test_dedupe.py` (111 lines)
- `test_cache.py` (59 lines)
- `test_dates.py` (114 lines)
- `test_openai_reddit.py` (77 lines)
- `test_render.py` (116 lines)

**No tests exist for the core `recon/`, `scoring/`, or `scripts/` modules.** These modules are entirely untested.

## Test Location & Organization

**Location:** `skills/last30days/tests/` — tests are NOT co-located with source files; they live in a dedicated `tests/` directory

**Mirrors source structure:** Each test file corresponds to one module in `skills/last30days/scripts/lib/`:
| Test File | Source Module |
|-----------|---------------|
| `test_normalize.py` | `scripts/lib/normalize.py` |
| `test_score.py` | `scripts/lib/score.py` |
| `test_models.py` | `scripts/lib/models.py` |
| `test_dedupe.py` | `scripts/lib/dedupe.py` |
| `test_cache.py` | `scripts/lib/cache.py` |
| `test_dates.py` | `scripts/lib/dates.py` |
| `test_openai_reddit.py` | `scripts/lib/openai_reddit.py` |
| `test_render.py` | `scripts/lib/render.py` |

**Path setup pattern at top of every test file:**
```python
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from lib import normalize
```

## Test Structure

**Class organization:** One test class per function/feature area, named `Test{FunctionName}`:
- `TestNormalizeRedditItems`, `TestNormalizeXItems`, `TestItemsToDicts` (`test_normalize.py`)
- `TestLog1pSafe`, `TestComputeRedditEngagementRaw`, `TestComputeXEngagementRaw`, `TestNormalizeTo100`, `TestScoreRedditItems`, `TestScoreXItems`, `TestSortItems` (`test_score.py`)
- `TestParseVersion`, `TestIsMainlineOpenAIModel`, `TestSelectOpenAIModel`, `TestSelectXAIModel`, `TestGetModels` (`test_models.py`)
- `TestNormalizeText`, `TestGetNgrams`, `TestJaccardSimilarity`, `TestFindDuplicates`, `TestDedupeItems` (`test_dedupe.py`)
- `TestGetCacheKey`, `TestCachePath`, `TestCacheValidity`, `TestModelCache` (`test_cache.py`)
- `TestGetDateRange`, `TestParseDate`, `TestTimestampToDate`, `TestGetDateConfidence`, `TestDaysAgo`, `TestRecencyScore` (`test_dates.py`)
- `TestIsModelAccessError`, `TestModelFallbackOrder` (`test_openai_reddit.py`)
- `TestRenderCompact`, `TestRenderContextSnippet`, `TestRenderFullReport`, `TestGetContextPath` (`test_render.py`)

**Test method naming:** Snake_case describing what's tested:
```python
def test_normalizes_basic_item(self):
def test_sets_low_confidence_for_old_date(self):
def test_handles_engagement(self):
```

**Standard TestCase structure:**
```python
class TestScoreRedditItems(unittest.TestCase):
    def test_scores_items(self):
        # Arrange
        items = [...]
        # Act
        result = score.score_reddit_items(items)
        # Assert
        self.assertEqual(len(result), 2)
        self.assertGreater(result[0].score, 0)
```

**No setup/teardown patterns:** No `setUp()` or `tearDown()` methods used in any test file. Each test method is fully self-contained.

## Test Coverage

**What is tested (skills/last30days):**
- `normalize.py`: Normalization of Reddit and X (Twitter) items, dict conversion, date confidence logic
- `score.py`: Safe log1p, engagement raw computation, normalization, composite scoring for Reddit/X, sorting
- `models.py`: OpenAI/XAI model selection, version parsing, mainline model detection, model get
- `dedupe.py`: Text normalization, n-gram generation, Jaccard similarity, duplicate detection, deduplication with score retention
- `cache.py`: Cache key generation, cache path construction, validity checks, model cache
- `dates.py`: Date range calculation, date parsing (ISO + timestamp), date confidence, recency scoring
- `openai_reddit.py`: Model access error detection patterns, fallback model constants
- `render.py`: Compact/full report rendering, context snippet rendering

**What is NOT tested:**
- **Entire `recon/` module** — `recon/config.py`, `recon/bridge.py`, `recon/tracker.py` (0 tests)
- **Entire `scoring/` module** — `scoring/engine.py`, `scoring/rescore.py` (0 tests)
- **Entire `scripts/` module** — `scripts/generate-pdf.py`, `scripts/fetch-ig-insights.py`, `scripts/fetch-yt-analytics.py` (0 tests)
- **Entire `recon/skeleton_ripper/`** — `pipeline.py`, `extractor.py`, `llm_client.py`, `aggregator.py`, `synthesizer.py`, `cache.py`, `prompts.py` (0 tests)
- **Entire `recon/storage/`** — `database.py` (SQLite init), `models.py` (CRUD) (0 tests)
- **Entire `recon/utils/`** — `logger.py` (requires filesystem), `state_manager.py` (requires filesystem) (0 tests)
- **Entire `recon/web/`** — Flask routes (`app.py`) (0 tests)
- **Integration tests:** No end-to-end or integration tests exist for any pipeline workflow

**Coverage risk summary:** The `recon/` and `scoring/` packages constitute the core business logic of the project and have zero test coverage. The `scoring/engine.py` (292 lines) with its multi-tier scoring algorithm is the highest-risk untested component.

## Test Patterns

**Pure function testing:** All tests test pure functions (no side effects, no I/O):
```python
# test_score.py:62-67
def test_normalizes_values(self):
    values = [0, 50, 100]
    result = score.normalize_to_100(values)
    self.assertEqual(result[0], 0)
    self.assertEqual(result[1], 50)
    self.assertEqual(result[2], 100)
```

**Mock/test data inline:** Test inputs are constructed inline as inline dicts or dataclass instances within each test method. No external fixture files are loaded.

**Model/API mocking:** `mock_models` parameter pattern for model API tests (`test_models.py:55-58`, `test_models.py:116-131`):
```python
# test_models.py:55-65
def test_auto_with_mock_models(self):
    mock_models = [
        {"id": "gpt-5.2", "created": 1704067200},
        {"id": "gpt-5.1", "created": 1701388800},
        {"id": "gpt-5", "created": 1698710400},
    ]
    result = models.select_openai_model("fake-key", policy="auto", mock_models=mock_models)
    self.assertEqual(result, "gpt-5.2")
```

**Boundary/edge case testing:**
- Empty lists: `def test_empty_list(self)` — `score.score_reddit_items([])` returns `[]`
- None values: `def test_none(self)` — `log1p_safe(None)` returns 0
- Negative values: `def test_negative(self)` — `log1p_safe(-5)` returns 0
- Nonexistent files: `def test_nonexistent_file_is_invalid(self)` — `is_cache_valid(fake_path)` returns `False`
- Single items: `def test_single_value(self)` — `normalize_to_100([50])` returns `[50]`

**Sorting stability:**
```python
# test_score.py:155-164
def test_stable_sort(self):
    items = [
        schema.RedditItem(id="R1", title="A", url="", subreddit="", score=50),
        schema.RedditItem(id="R2", title="B", url="", subreddit="", score=50),
    ]
    result = score.sort_items(items)
    self.assertEqual(len(result), 2)
```

## Test Fixtures / Data

**No external fixture files used in tests:** All test data is constructed inline. The `skills/last30days/fixtures/` directory exists with real sample data:
- `openai_sample.json`
- `xai_sample.json`
- `reddit_thread_sample.json`
- `models_openai_sample.json`
- `models_xai_sample.json`

These fixtures are NOT used by any test file. They appear to be manual sample data for development/debugging purposes.

**Data construction pattern:** Tests construct pydantic-style dataclass instances inline:
```python
# test_dedupe.py:84-90
items = [
    schema.RedditItem(id="R1", title="Best practices for skills", url="", subreddit="", score=90),
    schema.RedditItem(id="R2", title="Best practices for skills guide", url="", subreddit="", score=50),
]
result = dedupe.dedupe_items(items, threshold=0.6)
```

**No factory/builder pattern:** Each test constructs its own data manually. No shared factory functions or test fixtures.

**No conftest or pytest fixtures:** Project uses `unittest` only — no pytest fixtures, no `conftest.py`.

## CI Integration

**No CI pipeline detected:** No `.github/workflows/`, `.circleci/`, `Jenkinsfile`, or any CI configuration files exist.

**No test runner config:** No `jest.config.*`, `vitest.config.*`, `pytest.ini`, `setup.cfg`, or `tox.ini` exist.

**No pre-commit hooks:** No `.pre-commit-config.yaml` or git hooks for running tests before commit.

**Tests must be run manually:**
```bash
python3 -m unittest discover skills/last30days/tests -v
```

## Code Quality Tooling

**No linter config:** No `.eslintrc*`, `.pylintrc`, `pyproject.toml` with linter settings, `.flake8`, or `ruff.toml` detected.

**No formatter config:** No `.prettierrc*`, `biome.json`, `pyproject.toml` with formatter settings detected.

**Code quality relies on:** The `unittest` tests mentioned above and manual code review. CONTRIBUTING.md states "Follow PEP 8" as the only Python style guideline.

---

*Testing analysis: 2026-07-09*