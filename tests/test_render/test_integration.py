"""Integration tests for the full render pipeline."""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from agent_core.render.pipeline import RenderPipeline


class TestRenderPipelineIntegration:
    """Full pipeline integration tests."""

    def _make_scene_clip(self, sid, pd):
        """Helper: create a mock scene clip file and return its path."""
        clip = pd / "render" / "scenes" / f"{sid}.mp4"
        clip.parent.mkdir(parents=True, exist_ok=True)
        clip.write_text("mock clip", encoding="utf-8")
        return clip

    def _make_master(self, pd):
        """Helper: create a mock master video file and return its path."""
        master = pd / "render" / "final" / "master.mp4"
        master.parent.mkdir(parents=True, exist_ok=True)
        master.write_text("mock master", encoding="utf-8")
        return master

    def test_full_pipeline_mocked(self, tmp_path, mock_ffmpeg_available):
        """Full pipeline: load scenes → render → assemble → (no subtitles) → formats."""
        production_dir = tmp_path / "channels" / "ChannelA" / "active_production" / "prod_001"
        production_dir.mkdir(parents=True, exist_ok=True)

        script = {"scenes": [
            {"scene_id": "scene_01", "scene_number": 1, "text": "Scene one text."},
            {"scene_id": "scene_02", "scene_number": 2, "text": "Scene two text."},
        ]}
        (production_dir / "script.json").write_text(
            json.dumps(script), encoding="utf-8",
        )

        with patch("agent_core.render.pipeline._load_channel_config") as mock_cfg:
            mock_cfg.return_value = {
                "render": {
                    "width": 1920, "height": 1080, "fps": 30,
                    "transition_duration": 0.5, "output_formats": ["16:9", "9:16"],
                },
            }
            with patch("agent_core.render.pipeline.render_scene") as mock_render:
                mock_render.side_effect = lambda sid, pd, cfg, tl: self._make_scene_clip(sid, pd)

                pipeline = RenderPipeline("ChannelA", "prod_001")
                pipeline.production_dir = production_dir

                summary = pipeline.run()

                assert summary["total_scenes"] == 2
                assert summary["completed_scenes"] == 2
                assert summary["assembly"]["master_path"] is not None
                assert "16:9" in summary["assembly"]["formats"]
                assert "9:16" in summary["assembly"]["formats"]

    def test_pipeline_handles_no_subtitles_gracefully(self, tmp_path, mock_ffmpeg_available):
        """Pipeline should work without subtitle files."""
        production_dir = tmp_path / "channels" / "ChannelA" / "active_production" / "prod_002"
        production_dir.mkdir(parents=True, exist_ok=True)

        script = {"scenes": [
            {"scene_id": "scene_01", "scene_number": 1, "text": "Just one scene."},
        ]}
        (production_dir / "script.json").write_text(
            json.dumps(script), encoding="utf-8",
        )

        with patch("agent_core.render.pipeline._load_channel_config") as mock_cfg:
            mock_cfg.return_value = {"render": {"width": 1920, "height": 1080, "fps": 30}}
            with patch("agent_core.render.pipeline.render_scene") as mock_render:
                mock_render.side_effect = lambda sid, pd, cfg, tl: self._make_scene_clip(sid, pd)

                pipeline = RenderPipeline("ChannelA", "prod_002")
                pipeline.production_dir = production_dir
                summary = pipeline.run()

                assert summary["completed_scenes"] == 1
                assert summary["assembly"]["master_path"] is not None
                assert summary["assembly"]["subtitled_path"] is None

    def test_pipeline_resume_skips_completed(self, tmp_path, mock_ffmpeg_available):
        """Resume should skip already-checkpointed scenes."""
        production_dir = tmp_path / "channels" / "ChannelA" / "active_production" / "prod_003"
        production_dir.mkdir(parents=True, exist_ok=True)

        script = {"scenes": [
            {"scene_id": "scene_01", "scene_number": 1, "text": "Scene one."},
            {"scene_id": "scene_02", "scene_number": 2, "text": "Scene two."},
        ]}
        (production_dir / "script.json").write_text(
            json.dumps(script), encoding="utf-8",
        )

        with patch("agent_core.render.pipeline._load_channel_config") as mock_cfg:
            with patch("agent_core.render.pipeline.CheckpointManager") as mock_cp_mgr:
                cp_instance = MagicMock()
                mock_cp_mgr.return_value = cp_instance
                cp_instance.is_completed.side_effect = (
                    lambda stage, pid, scene_id=None: scene_id == "scene_01"
                )

                pipeline = RenderPipeline("ChannelA", "prod_003")
                pipeline.production_dir = production_dir
                with patch("agent_core.render.pipeline.render_scene") as mock_render:
                    mock_render.side_effect = lambda sid, pd, cfg, tl: self._make_scene_clip(sid, pd)

                    with patch("agent_core.render.assembly.FFmpegUtils.scene_duration", return_value=10.0):
                        summary = pipeline.run()

                        assert summary["completed_scenes"] == 2
