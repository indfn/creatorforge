# Testing Patterns

**Analysis Date:** 2026-07-10

## Test Framework

**Python Tests:**
- **Framework:** `unittest` (stdlib) — No pytest found in dependencies or configuration
- **Run Command:** `python3 -m unittest discover` or `python3 path/to/test_file.py`
- **No test runner configuration files** detected (no `pyproject.toml`, `setup.cfg`, `pytest.ini`, or `tox.ini`)

**JavaScript Tests** (in `.agents/skills/` only):
- **Framework:** Node.js built-in `node:test` module
- **Assertion Library:** Node.js built-in `node:assert` (strict mode)
- **Run Command:** `node --test path/to/test_file.mjs`
- **No Jest/Mocha/Vitest** dependency detected

**Node.js package.json** (`.opencode/package.json`): No test scripts or test dependencies defined.

## Test File Organization

**Location:**
- Python tests are placed in a `tests/` subdirectory within their skill/component directory — NOT co-located with source
- Example: `.agents/skills/last30days/tests/test_score.py`
- Example: `.agents/skills/last30days/tests/test_openai_reddit.py`
- JavaScript tests use `.test.mjs` suffix and are placed alongside their source files in `scripts/lib/`
- Example: `.agents/skills/media-use/scripts/lib/usage.test.mjs`
- Example: `.agents/skills/media-use/audio/scripts/lib/tts.test.mjs`

**Critical gap:** Core Python modules (`agent_core/`, `production/`, `scripts/`, `schemas/`) have NO test files whatsoever.

**Naming:**
- Python: `test_*.py` — e.g., `test_score.py`, `test_cache.py`, `test_render.py`
- JavaScript: `*.test.mjs` — e.g., `usage.test.mjs`, `tts.test.mjs`, `sfx.test.mjs`

**Directory structure (Python):**
```
.agents/skills/last30days/
├── scripts/
│   └── lib/
│       ├── score.py
│       ├── cache.py
│       └── ...
└── tests/
    ├── test_score.py
    ├── test_cache.py
    ├── test_render.py
    ├── test_openai_reddit.py
    └── ...
```

**Directory structure (JavaScript):**
```
.agents/skills/media-use/scripts/lib/
├── usage.mjs
├── usage.test.mjs
├── tts.mjs
├── tts.test.mjs
└── ...
```

## Test Structure (Python)

**Suite Organization — `unittest.TestCase`:**
```python
"""Tests for score module."""

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib import schema, score


class TestLog1pSafe(unittest.TestCase):
    def test_positive_value(self):
        result = score.log1p_safe(100)
        self.assertGreater(result, 0)

    def test_zero(self):
        result = score.log1p_safe(0)
        self.assertEqual(result, 0)

    def test_none(self):
        result = score.log1p_safe(None)
        self.assertEqual(result, 0)

    def test_negative(self):
        result = score.log1p_safe(-5)
        self.assertEqual(result, 0)


if __name__ == "__main__":
    unittest.main()
```

**Patterns:**
- One class per function/module area: `TestLog1pSafe`, `TestComputeRedditEngagementRaw`, `TestScoreRedditItems`
- Each test method is a single assertion or small group of related assertions
- SetUp/tearDown not observed (simple test data constructed inline)
- Test names are descriptive: `test_returns_false_for_non_400_error`, `test_handles_none`, `test_sorts_by_score_descending`
- Module-level docstring: `"""Tests for score module."""`

## Test Structure (JavaScript)

**Suite Organization — `node:test`:**
```javascript
import { strict as assert } from "node:assert";
import { test } from "node:test";
import { mkdtempSync, writeFileSync, rmSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { tagUsage, partitionUsage } from "./usage.mjs";

test("an asset referenced by a composition is marked in-use", () => {
  const dir = establish_temp_project(`<audio src="assets/bgm_001.wav"></audio>`);
  const tagged = tagUsage(records, dir);
  assert.equal(tagged.find((r) => r.id === "bgm_001").inUse, true);
  assert.equal(tagged.find((r) => r.id === "bgm_002").inUse, false);
});

test("partitionUsage splits used vs unused for the filter", () => {
  // ...
});
```

**Patterns:**
- Top-level `test()` calls (no describe/it nesting)
- Descriptive string labels: `"an asset referenced by a composition is marked in-use"`
- Temporary directories created in tests with cleanup via `try/finally`
- `assert.equal`, `assert.deepEqual`, `assert.match`, `assert.ok`

## Mocking

**Framework:** No mocking framework detected — no `unittest.mock`, `pytest-mock`, or `sinon.js` usage found.

**Patterns observed:**
- Tests test pure functions with no external dependencies
- No HTTP mocking, no database mocking, no file system mocking
- Some JS tests use temp directories with `mkdtempSync` to test file-system behavior (integration-style)
- No dependency injection patterns for testability in core modules

**Current limitation:** Tests only cover pure data-transformation functions. Modules that call external APIs, databases, or filesystems are untested.

## Fixtures and Factories

**Pattern:** Inline test data construction within test methods. No separate fixture files or factory functions.

**Example (Python):**
```python
def test_scores_items(self):
    today = datetime.now(timezone.utc).date().isoformat()
    items = [
        schema.RedditItem(
            id="R1",
            title="Test",
            url="https://reddit.com/r/test/1",
            subreddit="test",
            date=today,
            date_confidence="high",
            engagement=schema.Engagement(score=100, num_comments=50, upvote_ratio=0.9),
            relevance=0.9,
        ),
    ]
    result = score.score_reddit_items(items)
    self.assertEqual(len(result), 2)
```

**Example (JavaScript):**
```javascript
function project(html) {
  const dir = mkdtempSync(join(tmpdir(), "mu-usage-"));
  writeFileSync(join(dir, "index.html"), html);
  return dir;
}

const records = [
  { id: "bgm_001", path: ".media/audio/bgm/bgm_001.wav", description: "used track" },
  { id: "bgm_002", path: ".media/audio/bgm/bgm_002.wav", description: "orphan track" },
];
```

**Location:** No dedicated fixtures directory observed anywhere in the codebase.

## Coverage

**Requirements:** None enforced. No coverage tools configured (no `.coveragerc`, no `coverage.py` imports, no `nyc` in package.json).

**View Coverage:** Not possible without adding coverage tooling.

## Test Types

**Unit Tests:**
- Scope: Pure functions operating on in-memory data structures
- No imports of modules with side effects
- No HTTP, no database, no file system (except JS temp dir tests)
- Found in both Python (`last30days`) and JS (`media-use`) skill directories

**Integration Tests:**
- Not detected anywhere in the codebase
- No test fixtures against real APIs or databases

**E2E Tests:**
- Not used. No Cypress, Playwright, Selenium, or similar detected.

## Common Patterns

**Path Setup Pattern (Python):**
```python
import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib import http
```

**Main Guard (Python):**
```python
if __name__ == "__main__":
    unittest.main()
```

**Temporary Directory Cleanup (JavaScript):**
```javascript
const dir = mkdtempSync(join(tmpdir(), "mu-audio-"));
try {
  // test logic
} finally {
  rmSync(dir, { recursive: true, force: true });
}
```

**Assertion Patterns:**
- Python: `self.assertEqual(a, b)`, `self.assertIn(x, y)`, `self.assertIsInstance(x, y)`, `self.assertGreater(a, b)`, `self.assertTrue(x)`, `self.assertFalse(x)`, `self.assertIsNone(x)`, `self.assertNotEqual(a, b)`
- JS: `assert.equal(a, b)`, `assert.deepEqual(a, b)`, `assert.match(str, regex)`, `assert.ok(condition)`

## Test Coverage Gaps

| Area | Files | Test Status |
|------|-------|-------------|
| `agent_core/recon/` | 20+ Python files | **No tests** |
| `agent_core/scoring/` | 2 Python files | **No tests** |
| `agent_core/analytics/` | 3 Python files | **No tests** |
| `agent_core/publishing/` | 4 Python files | Stubs only |
| `production/` | 5 Python files | **No tests** |
| `scripts/` | 8 Python scripts | **No tests** |
| `schemas/` | 12 JSON Schemas | **No tests** |
| `.agents/skills/last30days/` | 8 test files | Unit tests present |
| `.agents/skills/media-use/` | 20+ test files | Unit tests present |

---

*Testing analysis: 2026-07-10*
