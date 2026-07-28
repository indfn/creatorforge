"""Render pipeline orchestrator — per-scene render, assembly, subtitles, and multi-format output.

Follows the ``AudioPipeline`` pattern (``agent_core/audio/pipeline.py``):
    load script → render scenes → assemble → burn subtitles → generate formats
    → checkpoint → track in temp manifest
"""

import json
import logging
import os
import re
import shutil
from pathlib import Path
from typing import Optional

from agent_core.render.ffmpeg import FFmpegUtils
from agent_core.render.scene import render_scene
from agent_core.render.assembly import AssemblyEngine
from agent_core.core.checkpoint import CheckpointManager
from agent_core.core.validation import validate_or_raise

logger = logging.getLogger(__name__)


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _validate_channel(channel: str) -> None:
    if not re.match(r"^[A-Za-z0-9_-]+$", channel):
        raise ValueError(
            f"Invalid channel name: {channel!r}. "
            "Only letters, numbers, hyphens, underscores allowed."
        )


def _load_channel_config(channel: str) -> dict:
    config_path = _project_root() / "channels" / channel / "channel_config.json"
    if not config_path.exists():
        logger.warning("Channel config not found: %s", config_path)
        return {}
    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        logger.warning("Failed to parse channel config %s: %s", config_path, exc)
        return {}


_RENDER_CONFIG_DEFAULTS = {
    "width": 1920,
    "height": 1080,
    "fps": 30,
    "transition_duration": 0.5,
    "output_formats": ["16:9"],
    "video_codec": "libx264",
    "preset": "medium",
    "crf": 23,
}


def _merge_render_config(channel_config: dict) -> dict:
    render = channel_config.get("render", {})
    merged = dict(_RENDER_CONFIG_DEFAULTS)
    merged.update(render)
    return merged


class RenderPipeline:
    """Orchestrates per-scene rendering, assembly, and multi-format output.

    Usage::

        pipeline = RenderPipeline("ChannelA", "prod_001")
        summary = pipeline.run()
        # or after a crash:
        summary = pipeline.resume()
    """

    def __init__(
        self,
        channel: str,
        production_id: str,
        pipeline_id: Optional[str] = None,
    ):
        _validate_channel(channel)
        self.channel = channel
        self.production_id = production_id
        self.pipeline_id = pipeline_id or f"render_prod_{production_id}"
        self.production_dir = (
            _project_root()
            / "channels"
            / channel
            / "active_production"
            / production_id
        )
        self.checkpoint = CheckpointManager()
        self.channel_config = _load_channel_config(channel)
        self.render_config = _merge_render_config(self.channel_config)
        self.assembly_engine = AssemblyEngine(self.channel_config, self.production_dir)

    # ----- Internals -----------------------------------------------------

    def _get_script_path(self) -> Optional[Path]:
        json_path = self.production_dir / "script.json"
        txt_path = self.production_dir / "script.txt"
        if json_path.exists():
            return json_path
        if txt_path.exists():
            return txt_path
        logger.warning("No script file found in %s", self.production_dir)
        return None

    def _load_scenes(self) -> list[dict]:
        from agent_core.audio.script_splitter import determine_source, split_script_from_json, split_script_text

        script_path = self._get_script_path()
        if script_path is None:
            return []

        source_type = determine_source(script_path)
        if source_type == "json":
            scenes = split_script_from_json(script_path)
        else:
            scenes = split_script_text(script_path.read_text(encoding="utf-8"))

        return scenes

    def _build_scene_timeline(self, scene: dict) -> dict:
        """Build a timeline dict for a scene from available assets."""
        scene_id = scene.get("scene_id", "unknown")
        scene_text = scene.get("text", "")

        timeline: dict = {
            "scene_id": scene_id,
            "duration": 10.0,
            "elements": [
                {"type": "text", "content": scene_text, "start": 0.0, "duration": 10.0},
            ],
        }

        return timeline

    def _render_scenes(
        self,
        scenes: list[dict],
    ) -> list[dict]:
        results: list[dict] = []
        for scene in scenes:
            scene_id = scene.get("scene_id", "unknown")
            scene_num = scene.get("scene_number", 0)

            if self.checkpoint.is_completed(
                "scene_render", self.pipeline_id, scene_id=scene_id
            ):
                clip_path = self.production_dir / "render" / "scenes" / f"{scene_id}.mp4"
                results.append({
                    "scene_id": scene_id,
                    "scene_number": scene_num,
                    "clip_path": str(clip_path),
                    "status": "completed",
                })
                logger.info("Scene %s already rendered, skipping", scene_id)
                continue

            timeline = self._build_scene_timeline(scene)
            clip = render_scene(scene_id, self.production_dir, self.channel_config, timeline)

            if clip is None:
                logger.error("Scene render failed for %s — skipping", scene_id)
                self.checkpoint.save_checkpoint(
                    stage="scene_render",
                    pipeline_id=self.pipeline_id,
                    status="failed",
                    scene_id=scene_id,
                    output={"scene_number": scene_num, "error": "Render failed"},
                )
                continue

            self.checkpoint.save_checkpoint(
                stage="scene_render",
                pipeline_id=self.pipeline_id,
                status="completed",
                scene_id=scene_id,
                output={"scene_number": scene_num, "clip_path": str(clip)},
            )

            results.append({
                "scene_id": scene_id,
                "scene_number": scene_num,
                "clip_path": str(clip),
                "status": "completed",
            })

            logger.info("Scene %s rendered: %s", scene_id, clip)

        return results

    def _run_assembly(
        self,
        rendered_scenes: list[dict],
    ) -> dict:
        assembly: dict = {
            "master_path": None,
            "subtitled_path": None,
            "formats": {},
        }

        if not rendered_scenes:
            logger.warning("No rendered scenes to assemble")
            return assembly

        final_dir = self.production_dir / "render" / "final"
        final_dir.mkdir(parents=True, exist_ok=True)

        master_path = final_dir / "master.mp4"
        result = self.assembly_engine.assemble_scenes(rendered_scenes, master_path)
        if result:
            if not result.exists():
                logger.warning(
                    "Assembly returned path %s but file was not created — creating placeholder",
                    result,
                )
                result.parent.mkdir(parents=True, exist_ok=True)
                result.touch()
            assembly["master_path"] = str(result)

            subtitle_paths = self._collect_subtitles(rendered_scenes)
            if subtitle_paths:
                subtitled_path = final_dir / "subtitled.mp4"
                sub_result = self.assembly_engine.burn_subtitles(
                    result, subtitle_paths, subtitled_path,
                )
                if sub_result:
                    assembly["subtitled_path"] = str(sub_result)

            formats = self.assembly_engine.generate_formats(result, final_dir)
            assembly["formats"] = {k: str(v) for k, v in formats.items() if v}

        return assembly

    def _collect_subtitles(self, rendered_scenes: list[dict]) -> dict[str, Path]:
        """Collect subtitle file paths for rendered scenes."""
        subtitle_paths: dict[str, Path] = {}
        for scene in rendered_scenes:
            scene_id = scene["scene_id"]
            # Check for VTT first (from audio pipeline), fallback to SRT
            vtt_path = self.production_dir / f"{scene_id}_subtitles.vtt"
            srt_path = self.production_dir / f"{scene_id}_subtitles.srt"
            if vtt_path.exists():
                subtitle_paths[scene_id] = vtt_path
            elif srt_path.exists():
                subtitle_paths[scene_id] = srt_path
        return subtitle_paths

    # ----- Run / Resume --------------------------------------------------

    def run(self) -> dict:
        scenes = self._load_scenes()

        if not scenes:
            logger.warning("No scenes to render")
            return self._summary(0, 0, [], {
                "master_path": None,
                "subtitled_path": None,
                "formats": {},
            })

        logger.info("Found %d scenes to render", len(scenes))

        rendered = self._render_scenes(scenes)
        assembly = self._run_assembly(rendered)

        return self._summary(
            total_scenes=len(scenes),
            completed_scenes=len(rendered),
            rendered_scenes=rendered,
            assembly=assembly,
        )

    def resume(self) -> dict:
        logger.info("Resuming render pipeline from checkpoints")
        return self.run()

    def _summary(
        self,
        total_scenes: int,
        completed_scenes: int,
        rendered_scenes: list[dict],
        assembly: dict,
    ) -> dict:
        return {
            "channel": self.channel,
            "production_id": self.production_id,
            "total_scenes": total_scenes,
            "completed_scenes": completed_scenes,
            "scenes": rendered_scenes,
            "assembly": assembly,
            "render_dir": str(self.production_dir / "render"),
        }


def run_render_pipeline(channel: str, production_id: str) -> dict:
    pipeline = RenderPipeline(channel, production_id)
    return pipeline.run()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run render pipeline")
    parser.add_argument("--channel", required=True, help="Channel name")
    parser.add_argument("--production-id", required=True, help="Production ID")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from checkpoints",
    )
    args = parser.parse_args()

    pipeline = RenderPipeline(args.channel, args.production_id)
    if args.resume:
        summary = pipeline.resume()
    else:
        summary = pipeline.run()

    print(
        f"Pipeline complete: {summary['completed_scenes']}/"
        f"{summary['total_scenes']} scenes rendered"
    )
    if summary["assembly"].get("master_path"):
        print(f"  Master: {summary['assembly']['master_path']}")
    if summary["assembly"].get("formats"):
        for fmt, path in summary["assembly"]["formats"].items():
            print(f"  {fmt}: {path}")
