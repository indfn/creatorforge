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
    stages: dict[str, str] = field(default_factory=dict)
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
        self._stage_list = stages
        self.pipeline_id = pipeline_id or f"pipe_{uuid.uuid4().hex[:12]}"
        self.checkpoint = checkpoint_manager or CheckpointManager()

        for stage in stages:
            for dep in stage.depends_on:
                if dep not in self.stages:
                    raise ValueError(f"Stage '{stage.name}' depends on unknown stage '{dep}'")

        self._execution_order = self._topological_sort()

    def _topological_sort(self) -> list[str]:
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
        return self._execute(input_config, on_progress, stage_kwargs, resume=False)

    def resume(
        self,
        input_config: dict,
        on_progress: Optional[Callable] = None,
        stage_kwargs: Optional[dict[str, dict]] = None,
    ) -> PipelineResult:
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

                if resume and self.checkpoint.is_completed(stage_name, self.pipeline_id, config=input_config):
                    cp = self.checkpoint.load_checkpoint(stage_name, self.pipeline_id)
                    result.stages[stage_name] = "skipped"
                    result.stage_outputs[stage_name] = cp.output if cp else None
                    if on_progress:
                        on_progress({"stage": stage_name, "status": "skipped"})
                    continue

                if on_progress:
                    on_progress({"stage": stage_name, "status": "running"})

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
