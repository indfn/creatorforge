---
title: "Pipeline Orchestrator with Checkpoint & Resume"
wave: 1
requirements: [PIPE-01, PIPE-02, PIPE-03]
depends_on: []
files_modified:
  - agent_core/core/__init__.py
  - agent_core/core/pipeline.py
  - agent_core/core/checkpoint.py
  - agent_core/core/validation.py
  - schemas/pipeline-stage.schema.json
  - schemas/checkpoint.schema.json
autonomous: true
---

## Objective

Create the foundational pipeline orchestration system: a generic DAG-based runner with typed, schema-validated checkpoints between stages and automatic resume from crashes.

## Background

The existing `SkeletonRipperPipeline` at `agent_core/recon/skeleton_ripper/pipeline.py` is a hardcoded 5-stage sequential pipeline with no checkpointing — if it crashes mid-way, all progress is lost. Phase 1 builds a reusable `PipelineOrchestrator` that any pipeline (recon, production, publishing) can use, with automatic checkpoint/resume built in.

New `agent_core/core/` package created alongside existing `agent_core/recon/` — serves as the foundation module.

## Tasks

### Task 1.1: Create `agent_core/core/` package

<read_first>
- agent_core/__init__.py
- agent_core/recon/skeleton_ripper/pipeline.py (existing pattern)
</read_first>

<action>
Create `agent_core/core/__init__.py`:
```python
"""Core infrastructure — pipeline orchestration, checkpointing, validation."""
```
</action>

<acceptance_criteria>
- `agent_core/core/__init__.py` exists and is importable: `from agent_core.core import ...` works
- `agent_core/core/` is a proper Python package with `__init__.py`
</acceptance_criteria>

---

### Task 1.2: Define JSON Schemas for Pipeline Stages and Checkpoints

<read_first>
- schemas/production-order.schema.json (existing schema for reference)
- schemas/topic.schema.json (existing schema pattern)
</read_first>

<action>

Create `schemas/pipeline-stage.schema.json`:
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Pipeline Stage",
  "description": "A single stage in a pipeline DAG — defines its name, input contract, output contract, and dependencies",
  "type": "object",
  "required": ["name", "output_schema", "depends_on"],
  "properties": {
    "name": { "type": "string", "pattern": "^[a-z_]+$" },
    "description": { "type": "string" },
    "output_schema": { "type": "string", "description": "Filename in schemas/ that stage output must validate against" },
    "depends_on": { "type": "array", "items": { "type": "string" }, "description": "Stage names that must complete before this one" },
    "timeout_seconds": { "type": "integer", "default": 300 }
  }
}
```

Create `schemas/checkpoint.schema.json`:
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Pipeline Checkpoint",
  "description": "Typed checkpoint artifact persisted between pipeline stages — enables resume",
  "type": "object",
  "required": ["stage", "pipeline_id", "status", "created_at", "content_hash"],
  "properties": {
    "stage": { "type": "string" },
    "pipeline_id": { "type": "string" },
    "scene_id": { "type": "string", "description": "Optional — scene-level sub-key for scene-granular checkpoints" },
    "status": { "type": "string", "enum": ["completed", "failed", "running"] },
    "output": { "type": ["object", "array", "null"], "description": "Validated stage output artifact" },
    "output_schema": { "type": "string", "description": "Schema used for validation" },
    "created_at": { "type": "string", "format": "date-time" },
    "content_hash": { "type": "string", "description": "SHA-256 of stage input config — detects stale checkpoints on config change" },
    "error": { "type": "string" }
  }
}
```

</action>

<acceptance_criteria>
- `schemas/pipeline-stage.schema.json` exists and is valid JSON Schema (draft-07)
- `schemas/checkpoint.schema.json` exists and is valid JSON Schema (draft-07)
- Both files pass `python -m json.tool <file>` without error
- `pipeline-stage.schema.json` requires `name`, `output_schema`, `depends_on`
- `checkpoint.schema.json` requires `stage`, `pipeline_id`, `status`, `created_at`, `content_hash`
</acceptance_criteria>

---

### Task 1.3: Implement Schema Validation Gate

<read_first>
- schemas/pipeline-stage.schema.json (new)
- schemas/production-order.schema.json (existing)
- pathlib usage patterns in agent_core/recon/config.py
</read_first>

<action>

Create `agent_core/core/validation.py` with:

```python
"""
Schema validation gate — validates pipeline artifacts against JSON Schema contracts.
Used as a quality gate at every stage boundary.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
import json
import jsonschema  # add to requirements.txt if not present


SCHEMAS_DIR = Path(__file__).resolve().parent.parent.parent / "schemas"


@dataclass
class ValidationResult:
    success: bool
    errors: list[str] = field(default_factory=list)
    data: Any = None


def load_schema(schema_name: str) -> dict:
    """Load a JSON Schema file from schemas/ directory."""
    path = SCHEMAS_DIR / schema_name
    if not path.exists():
        raise FileNotFoundError(f"Schema not found: {schema_name}")
    with open(path, "r") as f:
        return json.load(f)


def validate_output(data: Any, schema_name: str) -> ValidationResult:
    """
    Validate data against a named JSON Schema.
    
    Args:
        data: The artifact data to validate
        schema_name: Filename in schemas/ directory (e.g., "checkpoint.schema.json")
    
    Returns:
        ValidationResult with success flag and any validation errors
    """
    schema = load_schema(schema_name)
    try:
        jsonschema.validate(instance=data, schema=schema)
        return ValidationResult(success=True, data=data)
    except jsonschema.ValidationError as e:
        return ValidationResult(
            success=False,
            errors=[str(e)],
            data=data
        )


def validate_or_raise(data: Any, schema_name: str) -> Any:
    """Validate and return data, or raise ValueError on failure."""
    result = validate_output(data, schema_name)
    if not result.success:
        raise ValueError(f"Schema validation failed for {schema_name}: {'; '.join(result.errors)}")
    return data
```
</action>

<acceptance_criteria>
- `agent_core/core/validation.py` exists with `validate_output`, `validate_or_raise`, `load_schema` functions
- `from agent_core.core.validation import validate_output` works
- `validate_output({"name": "test", "output_schema": "x.json", "depends_on": []}, "pipeline-stage.schema.json")` returns `ValidationResult(success=True)`
- `validate_output({"invalid": True}, "pipeline-stage.schema.json")` returns `ValidationResult(success=False, errors=...)`
- Missing schema file raises `FileNotFoundError`
</acceptance_criteria>

---

### Task 1.4: Implement CheckpointManager

<read_first>
- schemas/checkpoint.schema.json (new from Task 1.2)
- agent_core/recon/utils/state_manager.py (existing state pattern)
- agent_core/recon/tracker.py (existing JSON persistence)
</read_first>

<action>

Create `agent_core/core/checkpoint.py` with:

```python
"""
Checkpoint Manager — typed, schema-validated checkpoint persistence
for pipeline stage artifacts. Supports scene-level granularity.
"""

import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

from agent_core.core.validation import validate_output, validate_or_raise


CHECKPOINTS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "checkpoints"


@dataclass
class Checkpoint:
    stage: str
    pipeline_id: str
    status: str  # "completed" | "failed" | "running"
    created_at: str
    content_hash: str
    scene_id: Optional[str] = None
    output: Any = None
    output_schema: Optional[str] = None
    error: Optional[str] = None


class CheckpointManager:
    """
    Manages pipeline checkpoints with schema validation and file locking.
    
    Checkpoints stored at: data/checkpoints/{pipeline_id}/{stage_name}.json
    Scene-level: data/checkpoints/{pipeline_id}/{stage_name}/scene_{XX}.json
    """

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or CHECKPOINTS_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _checkpoint_path(self, pipeline_id: str, stage: str, scene_id: Optional[str] = None) -> Path:
        stage_dir = self.base_dir / pipeline_id
        if scene_id:
            stage_dir = stage_dir / stage
            stage_dir.mkdir(parents=True, exist_ok=True)
            return stage_dir / f"{scene_id}.json"
        stage_dir.mkdir(parents=True, exist_ok=True)
        return stage_dir / f"{stage}.json"

    def _compute_hash(self, config: dict) -> str:
        """SHA-256 hash of stage input config — detects stale checkpoints."""
        raw = json.dumps(config, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()

    def save_checkpoint(
        self,
        stage: str,
        pipeline_id: str,
        status: str,
        output: Any = None,
        output_schema: Optional[str] = None,
        scene_id: Optional[str] = None,
        config: Optional[dict] = None,
        error: Optional[str] = None,
    ) -> Checkpoint:
        """
        Persist a checkpoint with schema validation.
        
        If output_schema is provided, output is validated before saving.
        """
        # Validate output against schema if provided
        if output is not None and output_schema:
            validate_or_raise(output, output_schema)

        checkpoint = Checkpoint(
            stage=stage,
            pipeline_id=pipeline_id,
            status=status,
            created_at=datetime.now(timezone.utc).isoformat(),
            content_hash=self._compute_hash(config or {}),
            scene_id=scene_id,
            output=output,
            output_schema=output_schema,
            error=error,
        )

        path = self._checkpoint_path(pipeline_id, stage, scene_id)
        # Write atomically: write to temp, then rename
        tmp_path = path.with_suffix(".tmp")
        with open(tmp_path, "w") as f:
            json.dump(asdict(checkpoint), f, indent=2, default=str)
        tmp_path.rename(path)

        return checkpoint

    def load_checkpoint(
        self,
        stage: str,
        pipeline_id: str,
        scene_id: Optional[str] = None,
    ) -> Optional[Checkpoint]:
        """Load checkpoint if it exists."""
        path = self._checkpoint_path(pipeline_id, stage, scene_id)
        if not path.exists():
            return None
        with open(path, "r") as f:
            data = json.load(f)
        return Checkpoint(**data)

    def is_completed(
        self,
        stage: str,
        pipeline_id: str,
        scene_id: Optional[str] = None,
        config: Optional[dict] = None,
    ) -> bool:
        """
        Check if a stage checkpoint exists with matching config hash.
        
        Returns True only if:
        1. Checkpoint exists
        2. Status is "completed"
        3. Config hash matches (detects stale checkpoints after config change)
        """
        cp = self.load_checkpoint(stage, pipeline_id, scene_id)
        if cp is None or cp.status != "completed":
            return False
        if config is not None and cp.content_hash != self._compute_hash(config):
            return False  # Config changed — checkpoint is stale
        return True

    def clear_pipeline(self, pipeline_id: str):
        """Remove all checkpoints for a pipeline ID."""
        path = self.base_dir / pipeline_id
        if path.exists():
            import shutil
            shutil.rmtree(path)

    def list_checkpoints(self, pipeline_id: str) -> list[Checkpoint]:
        """List all checkpoints for a pipeline."""
        path = self.base_dir / pipeline_id
        if not path.exists():
            return []
        result = []
        for item in path.iterdir():
            if item.is_file() and item.suffix == ".json":
                cp = self.load_checkpoint(item.stem, pipeline_id)
                if cp:
                    result.append(cp)
            elif item.is_dir():
                # Scene-level checkpoints
                for scene_file in item.glob("*.json"):
                    cp = self.load_checkpoint(item.name, pipeline_id, scene_file.stem)
                    if cp:
                        result.append(cp)
        return result
```
</action>

<acceptance_criteria>
- `agent_core/core/checkpoint.py` exists with `CheckpointManager` class and `Checkpoint` dataclass
- `from agent_core.core.checkpoint import CheckpointManager` works
- `save_checkpoint()` creates a valid JSON file at `data/checkpoints/{pipeline_id}/{stage}.json`
- `load_checkpoint()` returns the same data that was saved
- `is_completed()` returns True only for completed, matching-hash checkpoints
- Scene-level checkpoint saved to `data/checkpoints/{pipeline_id}/{stage}/scene_01.json`
- Scene-level `is_completed()` with `scene_id="scene_01"` works independently per scene
- `validate_or_raise` is called when `output_schema` is provided
- Checkpoint JSON validates against `checkpoint.schema.json` via `validate_output()`
</acceptance_criteria>

---

### Task 1.5: Implement PipelineOrchestrator

<read_first>
- agent_core/recon/skeleton_ripper/pipeline.py (existing pipeline pattern to learn from)
- schemas/pipeline-stage.schema.json (new from Task 1.2)
- agent_core/core/checkpoint.py (new from Task 1.4)
</read_first>

<action>

Create `agent_core/core/pipeline.py` with:

```python
"""
Generic Pipeline Orchestrator — DAG-based stage runner with checkpoint/resume.

Usage:
    pipeline = PipelineOrchestrator(
        stages=[Stage(name="scrape", ...), Stage(name="transcribe", ...)],
        pipeline_id="prod_001"
    )
    result = pipeline.run(input_config={"url": "..."})
    # On crash: same pipeline_id resumes from last checkpoint
    result = pipeline.resume(input_config={"url": "..."})
"""

import uuid
import time
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from typing import Any, Optional, Callable, Protocol

from agent_core.core.checkpoint import CheckpointManager
from agent_core.core.validation import validate_or_raise


class StageFn(Protocol):
    """Signature for a pipeline stage execution function."""
    def __call__(self, input_data: Any, on_progress: Optional[Callable] = None, **kwargs) -> Any:
        ...


@dataclass
class Stage:
    """A single pipeline stage in the DAG."""
    name: str
    description: str = ""
    fn: Optional[StageFn] = None
    output_schema: Optional[str] = None
    depends_on: list[str] = field(default_factory=list)
    timeout_seconds: int = 300


@dataclass
class PipelineResult:
    pipeline_id: str
    success: bool
    stages: dict[str, str] = field(default_factory=dict)  # stage_name -> status
    stage_outputs: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    started_at: str = ""
    completed_at: str = ""


class PipelineOrchestrator:
    """
    Generic DAG-based pipeline orchestrator with checkpoint/resume.
    
    Stages run in dependency order. Completed stages are skipped on resume
    if their checkpoint hash still matches the input config.
    """

    def __init__(
        self,
        stages: list[Stage],
        pipeline_id: Optional[str] = None,
        checkpoint_manager: Optional[CheckpointManager] = None,
    ):
        if not stages:
            raise ValueError("At least one stage is required")

        self.stages = {s.name: s for s in stages}
        self._stage_list = stages  # preserve order
        self.pipeline_id = pipeline_id or f"pipe_{uuid.uuid4().hex[:12]}"
        self.checkpoint = checkpoint_manager or CheckpointManager()

        # Validate DAG: no missing dependencies
        for stage in stages:
            for dep in stage.depends_on:
                if dep not in self.stages:
                    raise ValueError(f"Stage '{stage.name}' depends on unknown stage '{dep}'")

        # Topological sort
        self._execution_order = self._topological_sort()

    def _topological_sort(self) -> list[str]:
        """Return stage names in dependency order (simple Kahn's algorithm)."""
        in_degree = {s.name: 0 for s in self._stage_list}
        adj = {s.name: [] for s in self._stage_list}

        for stage in self._stage_list:
            for dep in stage.depends_on:
                adj[dep].append(stage.name)
                in_degree[stage.name] = in_degree.get(stage.name, 0) + 1

        queue = [name for name, deg in in_degree.items() if deg == 0]
        result = []
        while queue:
            node = queue.pop(0)
            result.append(node)
            for neighbor in adj[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(result) != len(self._stage_list):
            raise ValueError("Circular dependency detected in pipeline stages")
        return result

    def run(
        self,
        input_config: dict,
        on_progress: Optional[Callable] = None,
        stage_kwargs: Optional[dict[str, dict]] = None,
    ) -> PipelineResult:
        """
        Execute all stages in order, saving checkpoints after each.
        Skips stages that already have valid checkpoints (resume mode).
        
        Args:
            input_config: Pipeline input configuration (hashed for checkpoint matching)
            on_progress: Progress callback (called after each stage)
            stage_kwargs: Optional per-stage keyword arguments, keyed by stage name
        
        Returns:
            PipelineResult with stage outputs and status
        """
        return self._execute(input_config, on_progress, stage_kwargs, resume=False)

    def resume(
        self,
        input_config: dict,
        on_progress: Optional[Callable] = None,
        stage_kwargs: Optional[dict[str, dict]] = None,
    ) -> PipelineResult:
        """
        Resume from last checkpoint. Completed stages are skipped.
        Stages that were never started, failed, or have stale checkpoints are re-run.
        """
        return self._execute(input_config, on_progress, stage_kwargs, resume=True)

    def _execute(
        self,
        input_config: dict,
        on_progress: Optional[Callable],
        stage_kwargs: Optional[dict[str, dict]],
        resume: bool = False,
    ) -> PipelineResult:
        result = PipelineResult(
            pipeline_id=self.pipeline_id,
            success=True,
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        stage_kwargs = stage_kwargs or {}

        try:
            for stage_name in self._execution_order:
                stage = self.stages[stage_name]

                # Resume check: skip if already completed with matching config
                if resume and self.checkpoint.is_completed(stage_name, self.pipeline_id, config=input_config):
                    cp = self.checkpoint.load_checkpoint(stage_name, self.pipeline_id)
                    result.stages[stage_name] = "skipped"
                    result.stage_outputs[stage_name] = cp.output if cp else None
                    if on_progress:
                        on_progress({"stage": stage_name, "status": "skipped"})
                    continue

                if on_progress:
                    on_progress({"stage": stage_name, "status": "running"})

                # Collect inputs: config + outputs from dependency stages
                stage_input = dict(input_config)
                for dep in stage.depends_on:
                    if dep in result.stage_outputs:
                        stage_input[dep] = result.stage_outputs[dep]

                start = time.monotonic()
                try:
                    kwargs = stage_kwargs.get(stage_name, {})
                    if stage.fn is None:
                        raise ValueError(f"Stage '{stage_name}' has no execution function")

                    output = stage.fn(stage_input, on_progress=on_progress, **kwargs)

                    # Save checkpoint with schema validation
                    self.checkpoint.save_checkpoint(
                        stage=stage_name,
                        pipeline_id=self.pipeline_id,
                        status="completed",
                        output=output,
                        output_schema=stage.output_schema,
                        config=input_config,
                    )
                    result.stages[stage_name] = "completed"
                    result.stage_outputs[stage_name] = output

                except Exception as e:
                    self.checkpoint.save_checkpoint(
                        stage=stage_name,
                        pipeline_id=self.pipeline_id,
                        status="failed",
                        error=str(e),
                        config=input_config,
                    )
                    result.stages[stage_name] = "failed"
                    result.errors.append(f"[{stage_name}] {e}")
                    result.success = False
                    if on_progress:
                        on_progress({"stage": stage_name, "status": "failed", "error": str(e)})
                    break

                if on_progress:
                    elapsed = time.monotonic() - start
                    on_progress({"stage": stage_name, "status": "completed", "elapsed": elapsed})

        except Exception as e:
            result.success = False
            result.errors.append(str(e))

        result.completed_at = datetime.now(timezone.utc).isoformat()
        return result
```
</action>

<accepance_criteria>
- `agent_core/core/pipeline.py` exists with `PipelineOrchestrator`, `Stage`, `PipelineResult`, `StageFn`
- `from agent_core.core.pipeline import PipelineOrchestrator, Stage` works
- Pipeline with 3 stages runs all stages and returns `PipelineResult` with correct statuses
- After crash, `resume()` with same `input_config` skips completed stages (status="skipped")
- `resume()` re-runs failed stages
- Changing `input_config` makes existing checkpoints stale — stages re-run
- Circular dependency raises `ValueError`
- Missing dependency raises `ValueError`
- Stage timeout is tracked per stage
- On stage failure: pipeline stops, subsequent stages are not run, `result.success=False`
- Schema validation gate runs on stage output if `output_schema` is set
</acceptance_criteria>

---

### Task 1.6: Add `jsonschema` dependency to requirements

<read_first>
- requirements.txt
</read_first>

<action>
Add `jsonschema>=4.20.0` to `requirements.txt` if not already present. This is a new dependency for the schema validation gate.
</action>

<acceptance_criteria>
- `requirements.txt` contains `jsonschema>=4.20.0`
- `python -c "import jsonschema; print(jsonschema.__version__)"` exits 0 after install
</acceptance_criteria>

## Verification

1. Run `python -c "from agent_core.core.pipeline import PipelineOrchestrator, Stage; print('OK')"` — exits 0
2. Run `python -c "from agent_core.core.checkpoint import CheckpointManager; print('OK')"` — exits 0
3. Run `python -c "from agent_core.core.validation import validate_output, validate_or_raise; print('OK')"` — exits 0
4. Full integration test: define 3 stages (scrape → process → output), run pipeline, verify all 3 checkpoints exist in `data/checkpoints/{pipeline_id}/`
5. Resume test: run pipeline to completion, run `resume()` with same config — all 3 stages show "skipped"
6. Crash resume test: run pipeline, delete one checkpoint file manually, run `resume()` — the deleted stage re-runs, subsequent completed stages stay skipped
7. Stale config test: run pipeline, run `resume()` with different `input_config` — all stages re-run
8. Circular dep test: `PipelineOrchestrator(stages=[Stage("a", depends_on=["b"]), Stage("b", depends_on=["a"])])` raises `ValueError`

## Must Haves

- [ ] Pipeline runs stages in correct dependency order
- [ ] Checkpoints persist between runs and survive process restart
- [ ] Resume skips completed stages (with matching config hash)
- [ ] Schema validation gates reject invalid stage outputs
- [ ] Scene-level checkpoints nest independently
- [ ] `jsonschema` is a declared dependency

## Must Nots

- [ ] Do NOT modify existing `SkeletonRipperPipeline` — it will be migrated later
- [ ] Do NOT add any file locking yet (that's Plan 3)
- [ ] Do NOT add QuotaBudget integration (that's Plan 2)
