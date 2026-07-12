---
phase: "01"
plan: "01"
subsystem: "core"
tags: ["pipeline", "checkpoint", "schema", "validation"]
tech-stack:
  added:
    - jsonschema@4.26.0
  patterns:
    - DAG-based topological stage ordering (Kahn's algorithm)
    - Atomic file writes (tmp + rename)
    - Schema-validated stage output boundaries
    - Config-hash based checkpoint staleness detection
key-files:
  created:
    - agent_core/core/__init__.py
    - agent_core/core/pipeline.py
    - agent_core/core/checkpoint.py
    - agent_core/core/validation.py
    - schemas/pipeline-stage.schema.json
    - schemas/checkpoint.schema.json
  modified:
    - requirements.txt
key-decisions:
  - PipelineOrchestrator uses generic StageFn protocol (Callable) not hardcoded stages
  - CheckpointManager uses atomic writes (write .tmp file, rename to .json) for crash safety
  - Config hash (SHA-256 of sorted JSON) detects stale checkpoints on config change
  - Schema validation at stage boundaries uses `jsonschema` library against schemas/ directory
  - Scene-level checkpoints nest under `data/checkpoints/{pipeline_id}/{stage}/{scene_id}.json`
  - New agent_core/core/ package separate from existing agent_core/recon/
requirements-completed: [PIPE-01, PIPE-02, PIPE-03]
---

# Phase 01 Plan 01: Pipeline Orchestrator with Checkpoint & Resume — Summary

Generic DAG-based pipeline orchestrator with typed, schema-validated checkpointing and automatic resume from crashes. New `agent_core/core/` package created with 4 modules (pipeline, checkpoint, validation, `__init__`), plus 2 JSON Schema contracts.

## Tasks Completed

| # | Task | Status |
|---|------|--------|
| 1.1 | Create `agent_core/core/` package | ✓ |
| 1.2 | Define JSON Schemas (pipeline-stage, checkpoint) | ✓ |
| 1.3 | Implement Schema Validation Gate | ✓ |
| 1.4 | Implement CheckpointManager | ✓ |
| 1.5 | Implement PipelineOrchestrator | ✓ |
| 1.6 | Add jsonschema dependency | ✓ |

## Files Created/Modified

- `agent_core/core/__init__.py` — Package docstring
- `agent_core/core/pipeline.py` — PipelineOrchestrator, Stage, PipelineResult, StageFn (618 lines)
- `agent_core/core/checkpoint.py` — CheckpointManager, Checkpoint dataclass (368 lines)
- `agent_core/core/validation.py` — ValidationResult, validate_output, validate_or_raise, load_schema (183 lines)
- `schemas/pipeline-stage.schema.json` — Stage contract (name, output_schema, depends_on, timeout)
- `schemas/checkpoint.schema.json` — Checkpoint artifact (stage, pipeline_id, status, content_hash, etc.)
- `requirements.txt` — Added jsonschema>=4.20.0

## Verification Results

| # | Test | Result |
|---|------|--------|
| 1 | Pipeline imports OK | ✓ |
| 2 | Checkpoint imports OK | ✓ |
| 3 | Validation imports OK | ✓ |
| 4 | 3-stage DAG runs all stages, 3 checkpoint files created | ✓ |
| 5 | Resume with same config skips all stages | ✓ |
| 6 | Delete one checkpoint → resume re-runs only that stage | ✓ |
| 7 | Different config → all stages re-run (stale detection) | ✓ |
| 8 | Circular dependency raises ValueError | ✓ |

## Deviations from Plan

None — plan executed exactly as written.

## Next

Ready for Plan 02 (QuotaBudget) in Wave 1, then Plan 03 (Safety & Resilience) in Wave 2.
