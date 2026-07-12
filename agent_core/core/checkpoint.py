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
    status: str
    created_at: str
    content_hash: str
    scene_id: Optional[str] = None
    output: Any = None
    output_schema: Optional[str] = None
    error: Optional[str] = None


class CheckpointManager:
    """
    Manages pipeline checkpoints with schema validation.

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
        cp = self.load_checkpoint(stage, pipeline_id, scene_id)
        if cp is None or cp.status != "completed":
            return False
        if config is not None and cp.content_hash != self._compute_hash(config):
            return False
        return True

    def clear_pipeline(self, pipeline_id: str):
        path = self.base_dir / pipeline_id
        if path.exists():
            import shutil
            shutil.rmtree(path)

    def list_checkpoints(self, pipeline_id: str) -> list[Checkpoint]:
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
                for scene_file in item.glob("*.json"):
                    cp = self.load_checkpoint(item.name, pipeline_id, scene_file.stem)
                    if cp:
                        result.append(cp)
        return result
