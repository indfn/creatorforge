# Code Conventions

**Analysis Date:** 2026-07-09

## Naming Conventions

**Python files:** snake_case — e.g., `recon/config.py`, `scoring/engine.py`, `scripts/generate-pdf.py` (CONSISTENT across all modules)

**Classes:** PascalCase — e.g., `ReconLogger` (`recon/utils/logger.py:28`), `BatchedExtractor` (`recon/skeleton_ripper/extractor.py:35`), `SkeletonRipperPipeline` (`recon/skeleton_ripper/pipeline.py:102`), `StateManager` (`recon/utils/state_manager.py:24`), `Competitor` (`recon/config.py:21`), `LLMClient` (`recon/skeleton_ripper/llm_client.py:71`)

**Functions/methods:** snake_case — e.g., `load_competitors()` (`recon/config.py:42`), `get_logger()` (`recon/utils/logger.py:192`), `calculate_delay()` (`recon/utils/retry.py:26`), `score_topic()` (`scoring/engine.py:255`)

**Private functions:** Prefixed with underscore `_` — e.g., `_generate_topic_title()` (`recon/bridge.py:120`), `_tokenize()` (`scoring/engine.py:88`), `_extract_stems()` (`scoring/engine.py:111`), `_count_keyword_matches()` (`scoring/engine.py:93`)

**Modules (packages):** snake_case package names — `recon/`, `scoring/`, `recon.utils/`, `recon.storage/`, `recon.skeleton_ripper/`, `recon.web/`

**Constants:** UPPER_CASE — e.g., `ACTION_KEYWORDS` (`scoring/engine.py:16`), `OPINION_KEYWORDS` (`scoring/engine.py:23`), `BRAIN_FILE` (`scoring/engine.py:13`), `PIPELINE_DIR` (`recon/config.py:13`), `DATA_DIR` (`recon/config.py:14`)

**Dataclass fields:** snake_case — e.g., `llm_provider`, `whisper_model`, `max_attempts`, `initial_delay` (CONSISTENT across all `@dataclass` definitions)

**Enum values:** UPPER_CASE — e.g., `LogLevel.DEBUG` (`recon/utils/logger.py:20`), `JobStatus.PENDING` (`recon/skeleton_ripper/pipeline.py:40`), `JobPhase.SCRAPING` (`recon/utils/state_manager.py:15`)

**JSONL data files:** `{date}-topics.jsonl` pattern (`recon/bridge.py:204`), `scripts.jsonl`, `hooks.jsonl`, `angles.jsonl` — date-stamped for topics, simple name for others

**JSON schema files:** `topic.schema.json`, `angle.schema.json`, `hook.schema.json`, `script.schema.json` — dot-delimited format in `schemas/`

**Shell scripts:** kebab-case — e.g., `init-data.sh`, `run-recon-ui.sh`, `init-viral-command.sh`, `refresh-ig-token.sh`

## Code Style

**Python (PEP 8):** All Python files follow PEP 8 conventions. Evidence across all modules:
- 4-space indentation consistent
- Two blank lines between top-level definitions
- Single blank line between methods in a class
- Imports grouped: stdlib → third-party → local (see `recon/bridge.py:8-19`)

**Type hints used extensively:**

```python
# recon/config.py:9-10
from typing import Optional, Dict, List

@dataclass
class ReconConfig:
    competitors: List[Competitor]
    ig_username: Optional[str] = None
```
```python
# scoring/engine.py:255-261
def score_topic(
    title: str,
    description: str,
    views: int = 0,
    timeliness: int = 6,
    is_competitor: bool = False,
) -> Dict:
```

**Function length:** Varies widely — helper functions are short (2-15 lines), orchestrator functions are longer (50-80 lines like `score_topic()` at 37 lines, `_scrape_and_transcribe()` at 131 lines)

**Docstrings:** Module-level triple-quote docstrings on every file (`""" ... """`). Function-level docstrings on most public functions (one-line or multi-line). Private functions sometimes skip docstrings.

**Returns:** Explicit `return` statements. Functions that return `None` do not always annotate the return type.

**Error handling:** `try/except` with specific exception types, never bare `except:` — e.g., `except json.JSONDecodeError`, `except OSError`, `except requests.exceptions.HTTPError`

**JSON serialization:** Pattern of `json.dumps(obj, ensure_ascii=False)` for JSONL writes (`recon/bridge.py:223`, `scoring/rescore.py:97`), `json.dump(obj, f, indent=2)` for human-readable JSON (`recon/scripts/generate-pdf.py` pattern)

**Path handling:** `pathlib.Path` used throughout — `Path(__file__).parent` for relative path resolution (CONSISTENT across all Python files). Never `os.path.join` for path construction within packages.

**Sys.path manipulation:** Pattern of `sys.path.insert(0, str(Path(__file__).parent.parent))` used in entry-point scripts (`recon/bridge.py:18`, `scoring/rescore.py:17`, `recon/web/app.py:19`)

## File Organization

**Package structure:** Each package has an `__init__.py` with module docstring + explicit `__all__` exports (e.g., `recon/__init__.py`, `recon/utils/__init__.py`, `recon/storage/__init__.py`, `scoring/__init__.py`, `recon/skeleton_ripper/__init__.py`)

**Module grouping by domain:**
- `recon/config.py` — Configuration loading (competitors, credentials)
- `recon/bridge.py` — Skeleton-to-topic conversion bridge
- `recon/tracker.py` — Duplicate content tracking state
- `recon/utils/` — Cross-cutting utilities (logger, retry, state_manager)
- `recon/storage/` — SQLite database (database.py, models.py)
- `recon/skeleton_ripper/` — Multi-creator content analysis pipeline
- `recon/web/` — Flask UI dashboard
- `scoring/` — Topic scoring engine (ghost dependency, no external imports beyond stdlib+recon)
- `skills/last30days/` — Independent skill module with its own lib/ layout
- `scripts/` — CLI entry-point Python scripts

**One class per file:** Most substantial classes get their own file (e.g., `ReconLogger` in `logger.py`, `LLMClient` in `llm_client.py`, `SkeletonRipperPipeline` in `pipeline.py`). Smaller dataclasses co-exist in a single file when related (e.g., `Asset`, `Collection`, `AssetCollection` in `models.py`).

**Tests mirrored:** Tests in `skills/last30days/tests/` mirror the `scripts/lib/` structure — one test file per module (`test_score.py` → `score.py`, `test_dedupe.py` → `dedupe.py`, etc.)

## Error Handling Patterns

**Return vs. Exception:**
- Helper functions that query existence return empty/falsy values: `return []`, `return {}` (`recon/config.py:45`, `scoring/engine.py:39-50`)
- Pipeline operations raise exceptions with descriptive messages: `raise ValueError(f"Unknown provider: {provider}")` (`recon/skeleton_ripper/llm_client.py:77`), `raise RuntimeError("Instagram login failed...")` (`recon/skeleton_ripper/pipeline.py:221`)
- CLI scripts use `sys.exit(1)` with print for user-facing errors (`scripts/generate-pdf.py:290`, `scoring/rescore.py:27`)

**Structured logging in error handlers:**
```python
# recon/utils/retry.py:80-83
logger.error(category, f"All {config.max_attempts} attempts failed", {
    "function": fn.__name__,
    "final_error": str(e)
}, exception=e)
```

**Error code generation:** `ReconLogger.error()` and `.critical()` return unique error codes (`recon/utils/logger.py:64-67`):
```python
def _generate_error_code(self, category: str, message: str) -> str:
    hash_part = hashlib.md5(f"{category}:{message}".encode()).hexdigest()[:4].upper()
    return f"{category}-{timestamp_part:05d}-{hash_part}"
```

**Transaction rollback pattern for DB:**
```python
# recon/storage/database.py:93-104
@contextmanager
def db_transaction():
    conn = get_db_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
```

**File existence checks before operations:** Every file read checks `.exists()` first (CONSISTENT pattern across all modules — `recon/config.py:44`, `recon/tracker.py:25`, `scoring/engine.py:39`, `recon/bridge.py:31`)

## Documentation Patterns

**Module docstrings:** Every `.py` file starts with a triple-quoted module docstring (`""" ... """`) describing purpose and usage patterns:
```python
# recon/bridge.py:1-5
"""
Recon Bridge — Converts skeleton ripper output into JSONL topics
matching schemas/topic.schema.json for the content-pipeline discovery system.

This is the key integration point: competitor analysis → scored topics.
"""
```

**Function docstrings:** One-line summary for simple functions, multi-line with Args/Returns for complex ones:
```python
# scoring/engine.py:29-38
def load_brain_context() -> Dict:
    """
    Read agent-brain.json and return structured context for scoring.
    Returns dict with:
        icp_keywords: flattened list from icp.pain_points + goals + segments
        ...
    """
```

**"Ported from" annotations:** Modules ported from ReelRecon include a second-line note in the docstring: `recon/utils/logger.py:3`, `recon/utils/retry.py:2`, `recon/storage/database.py:3`

**Inline comments:** Used sparingly for non-obvious logic — section markers like `# =============================================================================` in `recon/web/app.py:56` and `recon/utils/logger.py` for route categories

**Data schemas:** JSON Schema draft-07 files in `schemas/` with `description` fields on all properties (`schemas/topic.schema.json`, `schemas/hook.schema.json`, etc.)

**Markdown command files:** Claude Code commands in `.claude/commands/viral-*.md` follow a structured phase-based format with Rules, Validation, and Persistence sections per CONTRIBUTING.md

**Structured CLI argument parsing:** `argparse` with `description` on every script — `scripts/generate-pdf.py:259`, `scoring/rescore.py:3-7`

## Logging / Observability

**Singleton custom logger:** `ReconLogger` singleton via `_instance` + `threading.Lock()` (`recon/utils/logger.py:31-38`)

**Global accessor:**
```python
# recon/utils/logger.py:192-196
def get_logger() -> ReconLogger:
    global _logger
    if _logger is None:
        _logger = ReconLogger()
    return _logger
```

**Log levels:** DEBUG, INFO, WARNING, ERROR, CRITICAL (enum with numeric values, `recon/utils/logger.py:20-25`)

**Dual output:**
- Console: Color-coded by level (`\033[90m` DEBUG, `\033[91m` ERROR, etc.) (`recon/utils/logger.py:108-121`)
- File: JSON-structured entries written to `data/recon/logs/recon.log` with timestamp, level, category, message, optional data/error_code

**Structured log format (JSONL):**
```json
{"timestamp": "2026-07-09 12:00:00.000", "level": "ERROR", "category": "EXTRACT", "message": "Batch extraction error", "error_code": "EXTRACT-12345-ABCD"}
```

**Error registry:** In-memory error code registry with `get_error_details()`, `get_recent_errors()` — useful for linking error codes to full context (`recon/utils/logger.py:56,179-185`)

**Logging in practice:**
```python
logger.info("BRIDGE", f"Generated {len(topics)} topics from {len(skeletons)} skeletons")  # recon/bridge.py:188
logger.error("UI", f"Push to discover failed", exception=e)  # recon/web/app.py:323
logger.warning("LLM", f"HTTP {status_code}, retrying in {delay:.1f}s")  # recon/skeleton_ripper/llm_client.py:113
```

**Module-level logger instantiation:** Every module creates its own logger at module level via `logger = get_logger()` — e.g., `recon/bridge.py:21`, `recon/utils/retry.py` (imports inside functions), `recon/skeleton_ripper/llm_client.py:15`

**File rotation:** `_rotate_if_needed()` — rotates at 10MB, keeps 5 files (`recon/utils/logger.py:49, 69-84`)

## Patterns & Idioms

**Dataclass-as-config:** Configuration objects defined as `@dataclass` with type-annotated fields and defaults:
- `RetryConfig` (`recon/utils/retry.py:14-23`)
- `ReconConfig` (`recon/config.py:29-39`)
- `JobConfig` / `JobProgress` / `JobResult` (`recon/skeleton_ripper/pipeline.py:51-99`)
- `Asset` / `Collection` (`recon/storage/models.py:14-25`)
- `Competitor` / `ModelInfo` / `ProviderConfig` (`recon/config.py:20-27`, `recon/skeleton_ripper/llm_client.py:18-31`)

**Enum-for-state-machine pattern:** Job states as Enum classes — `LogLevel` (`recon/utils/logger.py:20`), `JobPhase` (`recon/utils/state_manager.py:14`), `JobStatus` (`recon/skeleton_ripper/pipeline.py:40`)

**Decorator-based retry:** `retry_with_backoff` as a decorator with configurable params, plus pre-configured `network_retry` and `api_retry` partials (`recon/utils/retry.py:36-109`):
```python
@network_retry()
def some_network_call():
    ...
```

**Factory/creator functions at module level:**
- `create_job_config()` (`recon/skeleton_ripper/pipeline.py:404`)
- `run_skeleton_ripper()` (convenience wrapper, `recon/skeleton_ripper/pipeline.py:418`)
- `get_logger()` (singleton accessor, `recon/utils/logger.py:192`)

**singleton pattern:** `ReconLogger` uses double-checked locking singleton pattern (`recon/utils/logger.py:31-38`)

**sys.path patching for cross-package imports:** Entry-point scripts insert project root, enabling clean `from scoring.engine import score_topic` without package installation — used in `recon/bridge.py:18`, `scoring/rescore.py:17`, `recon/web/app.py:19`

**Path resolution pattern:** `Path(__file__).parent.parent.parent` pattern for navigating from deep modules to project root — e.g., `recon/utils/logger.py:46`, `recon/storage/database.py:10`, `recon/skeleton_ripper/pipeline.py:37`

**Callbacks for progress reporting:** `SkeletonRipperPipeline.run()` accepts optional `on_progress: Optional[Callable]` and passes via `_notify()` helper (`recon/skeleton_ripper/pipeline.py:116, 359-364`)

**Batch processing with binary search retry:** `BatchedExtractor._handle_parse_failure` splits failed batches in half recursively on parse error (`recon/skeleton_ripper/extractor.py:102-118`)

**JSONL append pattern:** Topic data saved as JSONL with duplicate ID checking — read existing IDs, write new ones (`recon/bridge.py:192-227`)

**Context manager for DB transactions:** `db_transaction()` context manager wrapping commit/rollback pattern (`recon/storage/database.py:93-104`)

**Class method factory pattern with `@classmethod`:**
```python
# recon/storage/models.py:27-43
@classmethod
def create(cls, type: str, title: str, ...) -> 'Asset':
    asset = cls(...)
    with db_transaction() as conn:
        conn.execute(...)
    return asset
```

---

*Convention analysis: 2026-07-09*