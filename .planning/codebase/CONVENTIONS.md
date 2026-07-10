# Coding Conventions

**Analysis Date:** 2026-07-10

## Language & Runtime

**Primary:** Python 3.10+ — all core logic in `agent_core/` and `production/`
**Secondary:** Bash — automation scripts in `scripts/` (`.sh` files), Node.js — test helpers in `.agents/skills/` (`.mjs` files)

## Naming Patterns

**Files:**
- Python: `snake_case.py` — e.g., `bridge.py`, `brain_updater.py`, `tts_generation.py`
- Bash: `kebab-case.sh` — e.g., `init-creatorforge.sh`, `refresh-ig-token.sh`
- JSON Schema: `kebab-case.schema.json` — e.g., `channel-config.schema.json`, `agent-brain.schema.json`
- Test files: `test_*.py` pattern — e.g., `test_score.py`, `test_cache.py`

**Functions:**
- Python: `snake_case` — e.g., `score_topic()`, `load_brain_pillars()`, `generate_topics_from_skeletons()`
- Private/internal helpers prefixed with underscore: `_generate_topic_title()`, `_match_pillars()`, `_tokenize()`
- Bash: `snake_case` in functions

**Classes:**
- Python: `PascalCase` — e.g., `InstaClient`, `ReconLogger`, `StateManager`, `SkeletonRipperPipeline`, `BatchedExtractor`
- Dataclasses: `PascalCase` — e.g., `Competitor`, `ReconConfig`, `JobConfig`, `JobProgress`, `JobResult`
- Enums: `PascalCase` with `UPPER_CASE` values — e.g., `LogLevel.INFO`, `JobStatus.PENDING`, `JobPhase.SCRAPING`

**Variables:**
- Python: `snake_case` — e.g., `brain_ctx`, `text_lower`, `error_code`
- Constants: `UPPER_SNAKE_CASE` — e.g., `ACTION_KEYWORDS`, `OPINION_KEYWORDS`, `BRAIN_FILE`, `PIPELINE_DIR`

**Types:**
- Modern Python 3.10+ style: `list[dict]`, `dict[str, float]`, `Optional[str]`, `str | None`
- Legacy style also present: `Optional[Dict]`, `List[str]`, `Dict[str, Any]` in older files

## Code Style

**Docstrings:**
- Module-level docstrings in every file (triple quotes `"""..."""`), describing the module's purpose
- Function docstrings with `Args:`, `Returns:`, `Raises:` sections using Google-style format
- Example from `agent_core/scoring/engine.py`:
```python
def score_topic(
    title: str,
    description: str,
    views: int = 0,
    timeliness: int = 6,
    is_competitor: bool = False,
) -> Dict:
    """
    Orchestrator: score a topic against the agent brain.

    Args:
        title: Topic title
        description: Topic description
        views: View count (for competitor bonus calculation)
        timeliness: Timeliness score (1-10), provided by caller
        is_competitor: Whether this is from competitor analysis

    Returns:
        Scoring dict matching topic.schema.json scoring object:
        {icp_relevance, timeliness, content_gap, proof_potential, total, weighted_total}
    """
```

**Linting:**
- No linter config files detected (no `.eslintrc`, `.pylintrc`, `pyproject.toml`, `setup.cfg`)
- `CONTRIBUTING.md` references PEP 8 but no automated linting is configured
- `production/RenderEngine/linter.py` is a domain-specific render validator, not a code linter

**Formatting:**
- No formatter config detected (no `.prettierrc`, `pyproject.toml` with black/isort config)
- Indentation: 4 spaces for Python (PEP 8 default)
- Maximum line length: not strictly enforced (~80 chars observed, with some lines up to ~100)

## Import Organization

**Python (stdlib first, then third-party, then local):**
```python
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

import instaloader
import requests

from agent_core.recon.config import load_competitors, BRAIN_FILE
from agent_core.recon.utils.logger import get_logger
```

**Observed ordering rules:**
1. Standard library imports
2. Third-party imports (separated by blank line)
3. Local/package imports (separated by blank line)
4. Within each group: alphabetical ordering is common but not strict

**Path resolution pattern** (used in scripts and entry points):
```python
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from agent_core.scoring.engine import score_topic
```

## Error Handling

**Patterns:**
- Explicit exception handling with `try/except`, never bare `except:`
- Custom structured logging with error codes via `ReconLogger.error()` and `.critical()` methods
- Retry with exponential backoff via `retry_with_backoff` decorator in `agent_core/recon/utils/retry.py`
- Error codes generated as: `"{category}-{timestamp:05d}-{hash_part}"` (e.g., `INSTA-84321-A3F2`)
- Stub functions raise `NotImplementedError("descriptive message")` for planned-but-unimplemented code

**Retry pattern** (from `agent_core/recon/utils/retry.py`):
```python
@retry_with_backoff(max_attempts=3, initial_delay=1.0, retryable_exceptions=(ConnectionError, TimeoutError, OSError))
def some_network_call():
    ...
```

**Pre-configured retry decorators:**
```python
network_retry = functools.partial(retry_with_backoff, max_attempts=3, initial_delay=1.0, ...)
api_retry = functools.partial(retry_with_backoff, max_attempts=3, initial_delay=2.0, max_delay=60.0, ...)
```

## Logging

**Framework:** Custom `ReconLogger` singleton (thread-safe) with file rotation and structured JSON output

**Pattern:**
- Module-level logger: `logger = get_logger()`
- Log with category: `logger.info("BRIDGE", f"Generated {len(topics)} topics")`
- Methods: `.debug()`, `.info()`, `.warning()`, `.error()`, `.critical()`
- `.error()` and `.critical()` accept `exception=e` for traceback capture and return an error code
- Categories are uppercase short strings: `"INSTA"`, `"YOUTUBE"`, `"TRANSCRIBE"`, `"BRIDGE"`, `"PIPELINE"`

**Console output format:** `[CATEGORY] message` or `[ERROR_CODE] message`
**File output format:** JSONL — `{"timestamp": "...", "level": "INFO", "category": "BRIDGE", "message": "...", "data": {...}}`

## Comments

**When to Comment:**
- Module-level docstrings explain what the module does and how to use it
- Complex logic (scoring tiers, fallback chains) gets inline comments
- "Ported from ReelRecon" annotations used where code was migrated from an older project
- Not over-commented: straightforward operations are self-documenting

**Comment style:**
- `#` inline comments with space after `#`
- Section separators in larger files: `# ====== SECTION NAME ======`

## Function Design

**Size:**
- Most functions are 10-60 lines
- Pipeline orchestration functions can be larger (100-200 lines) — `SkeletonRipperPipeline.run()` is the largest at ~80 lines
- Pure helper functions stay under 20 lines

**Parameters:**
- Named parameters with type hints
- Default values provided for optional params: `def score_topic(title: str, description: str, views: int = 0)`
- Keyword-only after `*` in some cases: `def retry_with_backoff(func=None, *, max_attempts=3, ...)`
- Dataclasses used for complex parameter groups (`@dataclass` classes like `JobConfig`, `ReconConfig`)

**Return Values:**
- Typed return values on all functions
- `Optional[str]` / `str | None` for nullable returns
- Dicts returned with matching JSON Schema shapes where applicable
- Functions that can fail return `None` or empty sentinel values

## Module Design

**Exports:**
- Most modules use `__all__` in `__init__.py` for explicit export control
- Selective imports from submodules (e.g., `from .pipeline import SkeletonRipperPipeline, create_job_config`)

**Barrel Files:**
- Every package has `__init__.py` with a module docstring and re-exports
- `__init__.py` files provide usage examples in their docstrings
- Sub-packages like `agent_core/recon/storage/__init__.py` re-export key classes

## Data Handling

**File I/O:**
- `pathlib.Path` used consistently (no `os.path.join()` in modern code)
- JSON: `json.dump(data, f, indent=2, ensure_ascii=False)` for writing
- JSONL: lines appended with `json.dumps(obj, ensure_ascii=False) + "\n"`
- File encoding: `encoding='utf-8'` on all file opens (both `'r'` and `'w'` modes)
- `with open(...)` context manager always used

**Configuration:**
- Dataclasses for typed config: `ReconConfig`, `JobConfig`, `RetryConfig`
- Env var loading via `python-dotenv` (.env file) with custom `.env` parser in `config.py`
- Credential priority: env vars > `.env` file > `.credentials` file
- Config merging pattern with fallback chains in `load_config()`

## Testing Conventions

**Test location:** Separate directories (`tests/`), co-located with skill/component, not alongside source
**Test framework:** Python uses `unittest` (stdlib), JavaScript uses `node:test` + `node:assert`

See `TESTING.md` for detailed testing patterns.

---

*Convention analysis: 2026-07-10*
