"""
Audio production pipeline — per-scene TTS generation, force alignment,
subtitle generation, and temp asset tracking.

Orchestrates the full per-scene workflow:
    split script → TTS (with fallback) → force align → generate subtitles
    → checkpoint → track in temp manifest

Checkpoints are saved per scene so the pipeline can resume after a crash
without re-processing completed scenes (PROD-AUDIO-04).  An individual
scene's TTS failure does not abort the pipeline — it logs the error and
continues to the next scene (T-09-03-01).
"""

import json
import logging
import os
import re
import shutil
from pathlib import Path
from typing import Optional

from agent_core.audio.tts import FallbackChain, _load_tts_config
from agent_core.audio.script_splitter import (
    determine_source,
    split_script_from_json,
    split_script_text,
    write_scene_scripts,
)
from agent_core.audio.alignment.aligner import force_align_scene
from agent_core.audio.subtitles.generator import generate_subtitle_files
from agent_core.audio.lifecycle import TempAssetManifest
from agent_core.core.checkpoint import CheckpointManager
from agent_core.core.validation import validate_or_raise

logger = logging.getLogger(__name__)


# =========================================================================
# Private helpers (standard pattern from publishing/uploader.py)
# =========================================================================


def _project_root() -> Path:
    """Resolve the project root directory (parent of ``agent_core/``)."""
    return Path(__file__).resolve().parent.parent.parent


def _validate_channel(channel: str) -> None:
    """Validate channel name to prevent path traversal.

    Raises:
        ValueError: If channel name contains invalid characters.
    """
    if not re.match(r"^[A-Za-z0-9_-]+$", channel):
        raise ValueError(
            f"Invalid channel name: {channel!r}. "
            "Only letters, numbers, hyphens, underscores allowed."
        )


def _load_channel_config(channel: str) -> dict:
    """Load the per-channel configuration JSON.

    Returns:
        Parsed ``channel_config.json`` dict, or empty dict on failure.
    """
    config_path = _project_root() / "channels" / channel / "channel_config.json"
    if not config_path.exists():
        logger.warning("Channel config not found: %s", config_path)
        return {}
    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        logger.warning("Failed to parse channel config %s: %s", config_path, exc)
        return {}


# =========================================================================
# AudioPipeline
# =========================================================================


class AudioPipeline:
    """Orchestrates per-scene audio production.

    Usage::

        pipeline = AudioPipeline("ChannelA", "prod_001")
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
        """Initialise the pipeline for a channel and production.

        Args:
            channel: Channel name (e.g. ``"ChannelA"``).
            production_id: Production identifier (e.g. ``"prod_001"``).
            pipeline_id: Optional explicit pipeline ID for checkpoint
                namespacing.  Defaults to ``"audio_prod_{production_id}"``.

        Raises:
            ValueError: If the channel name is invalid.
        """
        _validate_channel(channel)
        self.channel = channel
        self.production_id = production_id
        self.pipeline_id = pipeline_id or f"audio_prod_{production_id}"
        self.production_dir = (
            _project_root()
            / "channels"
            / channel
            / "active_production"
            / production_id
        )
        self.manifest = TempAssetManifest(self.production_dir)
        self.checkpoint = CheckpointManager()
        self.channel_config = _load_channel_config(channel)
        self.fallback_chain, self.provider_configs, self.voice_config = _load_tts_config(channel)

    # ----- Internals -----------------------------------------------------

    def _get_script_path(self) -> Optional[Path]:
        """Locate the script file in the production directory.

        Checks for ``script.json`` first, then ``script.txt``.

        Returns:
            Path to the script file, or ``None`` if neither exists.
        """
        json_path = self.production_dir / "script.json"
        txt_path = self.production_dir / "script.txt"
        if json_path.exists():
            logger.info("Found JSON script: %s", json_path)
            return json_path
        if txt_path.exists():
            logger.info("Found text script: %s", txt_path)
            return txt_path
        logger.warning("No script file found in %s", self.production_dir)
        return None

    @staticmethod
    def _get_scene_text(scene: dict) -> str:
        """Extract the plain text from a scene dict.

        Supports:
            - ``scene["text"]``
            - ``scene["say"]`` (list joined with spaces, or string directly)

        SSML/XML tags are stripped before returning.
        """
        text = scene.get("text", "")
        if not text and "say" in scene:
            say = scene["say"]
            if isinstance(say, list):
                text = " ".join(str(part) for part in say)
            elif isinstance(say, str):
                text = say

        # Strip SSML/XML tags (T-09-01-01)
        import re as _re
        text = _re.sub(r"<[^>]+>", "", text)
        return text

    # ----- Run / Resume --------------------------------------------------

    def run(self) -> dict:
        """Execute the full per-scene audio production pipeline.

        Returns:
            Summary dict with keys ``channel``, ``production_id``,
            ``total_scenes``, ``completed_scenes``, ``scenes`` (list of per-scene
            results), and ``temp_manifest_path``.

        Raises:
            FileNotFoundError: If no ``script.json`` or ``script.txt`` exists
                in the production directory.
        """
        # 1. Load script
        script_path = self._get_script_path()
        if script_path is None:
            raise FileNotFoundError(
                f"No script.json or script.txt found in {self.production_dir}"
            )

        # 2. Split script
        source_type = determine_source(script_path)
        if source_type == "json":
            scenes = split_script_from_json(script_path)
        else:
            scenes = split_script_text(script_path.read_text(encoding="utf-8"))

        logger.info("Found %d scenes in script (%s)", len(scenes), source_type)

        if not scenes:
            logger.warning("Script produced zero scenes — nothing to process")
            return {
                "channel": self.channel,
                "production_id": self.production_id,
                "total_scenes": 0,
                "completed_scenes": 0,
                "scenes": [],
                "temp_manifest_path": str(self.manifest.manifest_path),
            }

        # 3. Write per-scene script files
        write_scene_scripts(scenes, self.production_dir)

        # 4. Initialize TTS fallback chain
        tts_chain = FallbackChain(self.fallback_chain, self.provider_configs)

        # 5. Per-scene loop
        results: list[dict] = []
        for scene in scenes:
            scene_id = scene.get("scene_id", "unknown")
            scene_num = scene.get("scene_number", 0)

            # Checkpoint: skip if already completed
            if self.checkpoint.is_completed(
                "tts_generation", self.pipeline_id, scene_id=scene_id
            ):
                logger.info("Scene %s already completed, skipping", scene_id)
                continue

            # Step A: Generate audio via TTS fallback chain
            logger.info("Generating audio for %s", scene_id)
            scene_text = self._get_scene_text(scene)
            audio_result = tts_chain.generate(scene_text, self.voice_config)

            if audio_result is None:
                logger.error("All TTS providers failed for %s — skipping", scene_id)
                # Save failed checkpoint (T-09-03-01: one scene's failure
                # doesn't abort the pipeline).
                self.checkpoint.save_checkpoint(
                    stage="tts_generation",
                    pipeline_id=self.pipeline_id,
                    status="failed",
                    scene_id=scene_id,
                    output={
                        "scene_number": scene_num,
                        "error": "All TTS providers failed",
                    },
                )
                continue

            # Copy audio to production dir and clean up temp file
            audio_path = self.production_dir / f"{scene_id}_audio.wav"
            shutil.copy2(audio_result.audio_path, audio_path)
            try:
                os.unlink(audio_result.audio_path)
            except OSError:
                pass

            # Step B: Force align — rewrites _script.txt with inline timestamps
            script_file = self.production_dir / f"{scene_id}_script.txt"
            alignment = force_align_scene(Path(audio_path), script_file)
            if alignment is None:
                alignment = []

            # Step C: Generate subtitle files
            srt_vtt = generate_subtitle_files(
                alignment,
                str(self.production_dir / f"{scene_id}_subtitles"),
            )

            # Step D: Track temp assets
            self.manifest.add_scene_assets(
                scene_id=scene_id,
                audio_path=str(audio_path),
                srt_path=str(srt_vtt.get("srt", "")),
                vtt_path=str(srt_vtt.get("vtt", "")),
            )

            # Step E: Save checkpoint
            self.checkpoint.save_checkpoint(
                stage="tts_generation",
                pipeline_id=self.pipeline_id,
                status="completed",
                scene_id=scene_id,
                output={
                    "scene_number": scene_num,
                    "audio_path": str(audio_path),
                    "subtitle_count": len(alignment),
                },
            )

            results.append({
                "scene_id": scene_id,
                "audio": str(audio_path),
                "alignment_word_count": len(alignment),
                "status": "completed",
            })

            logger.info(
                "Scene %s complete: %d aligned words",
                scene_id,
                len(alignment),
            )

        # 6. Return summary
        return {
            "channel": self.channel,
            "production_id": self.production_id,
            "total_scenes": len(scenes),
            "completed_scenes": len(results),
            "scenes": results,
            "temp_manifest_path": str(self.manifest.manifest_path),
        }

    def resume(self) -> dict:
        """Resume the pipeline after a crash.

        Relies on checkpoint skipping for already-completed scenes.
        Same behaviour as :meth:`run` — completed scenes are skipped
        via :meth:`CheckpointManager.is_completed`.
        """
        logger.info("Resuming pipeline from checkpoints")
        return self.run()


# =========================================================================
# Module-level convenience function
# =========================================================================


def run_audio_pipeline(channel: str, production_id: str) -> dict:
    """Convenience function: create an ``AudioPipeline`` instance and run it.

    Args:
        channel: Channel name (e.g. ``"ChannelA"``).
        production_id: Production identifier (e.g. ``"prod_001"``).

    Returns:
        Summary dict from :meth:`AudioPipeline.run`.
    """
    pipeline = AudioPipeline(channel, production_id)
    return pipeline.run()


# =========================================================================
# CLI entry point
# =========================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run audio production pipeline")
    parser.add_argument("--channel", required=True, help="Channel name")
    parser.add_argument("--production-id", required=True, help="Production ID")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from checkpoints (skip already-completed scenes)",
    )
    args = parser.parse_args()

    pipeline = AudioPipeline(args.channel, args.production_id)
    if args.resume:
        summary = pipeline.resume()
    else:
        summary = pipeline.run()

    print(
        f"Pipeline complete: {summary['completed_scenes']}/"
        f"{summary['total_scenes']} scenes"
    )
    for s in summary["scenes"]:
        status = "\u2713" if s["status"] == "completed" else "\u2717"
        print(f"  {status} {s['scene_id']}: {s['alignment_word_count']} words")
