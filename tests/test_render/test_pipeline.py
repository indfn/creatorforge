"""Tests for RenderPipeline orchestrator."""

from pathlib import Path
from unittest.mock import patch

import pytest

from agent_core.render.pipeline import RenderPipeline


class TestRenderPipelineInit:
    """RenderPipeline.__init__"""

    def test_init_with_valid_channel(self, mock_render_pipeline_deps):
        pipeline = RenderPipeline("ChannelA", "prod_001")
        assert pipeline.channel == "ChannelA"
        assert pipeline.production_id == "prod_001"
        assert pipeline.pipeline_id == "render_prod_prod_001"

    def test_init_rejects_invalid_channel(self):
        with pytest.raises(ValueError, match="Invalid channel"):
            RenderPipeline("Channel/Bad", "prod_001")

    def test_init_creates_default_pipeline_id(self):
        pipeline = RenderPipeline("ChannelA", "test_001")
        assert pipeline.pipeline_id == "render_prod_test_001"

    def test_init_with_custom_pipeline_id(self):
        pipeline = RenderPipeline("ChannelA", "test_001", pipeline_id="custom_id")
        assert pipeline.pipeline_id == "custom_id"


class TestRenderPipelineConfig:
    """RenderPipeline render config"""

    def test_loads_render_config(self, mock_render_pipeline_deps):
        pipeline = RenderPipeline("ChannelA", "prod_001")
        assert pipeline.render_config["width"] == 1920
        assert pipeline.render_config["fps"] == 30

    def test_applies_defaults_when_no_render_section(self):
        with patch("agent_core.render.pipeline._load_channel_config", return_value={}):
            pipeline = RenderPipeline("ChannelA", "prod_001")
            assert pipeline.render_config["width"] == 1920
            assert pipeline.render_config["fps"] == 30
            assert pipeline.render_config["transition_duration"] == 0.5

    def test_merges_partial_config(self):
        with patch("agent_core.render.pipeline._load_channel_config", return_value={
            "render": {"width": 3840, "fps": 60},
        }):
            pipeline = RenderPipeline("ChannelA", "prod_001")
            assert pipeline.render_config["width"] == 3840
            assert pipeline.render_config["fps"] == 60
            assert pipeline.render_config["transition_duration"] == 0.5


class TestRenderPipelineRun:
    """RenderPipeline.run()"""

    def test_run_with_no_scenes(self, mock_render_pipeline_deps):
        pipeline = RenderPipeline("ChannelA", "prod_001")

        with patch.object(pipeline, "_load_scenes", return_value=[]):
            summary = pipeline.run()
            assert summary["total_scenes"] == 0
            assert summary["completed_scenes"] == 0
            assert summary["assembly"]["master_path"] is None

    def test_run_calls_render_for_each_scene(self, mock_render_pipeline_deps):
        pipeline = RenderPipeline("ChannelA", "prod_001")
        mock_scenes = [
            {"scene_id": "scene_01", "scene_number": 1, "text": "Text 1"},
            {"scene_id": "scene_02", "scene_number": 2, "text": "Text 2"},
        ]

        with patch.object(pipeline, "_load_scenes", return_value=mock_scenes):
            with patch.object(pipeline, "_render_scenes", return_value=[
                {"scene_id": "scene_01", "scene_number": 1, "clip_path": "/tmp/s1.mp4", "status": "completed"},
                {"scene_id": "scene_02", "scene_number": 2, "clip_path": "/tmp/s2.mp4", "status": "completed"},
            ]):
                with patch.object(pipeline, "_run_assembly", return_value={
                    "master_path": "/tmp/master.mp4",
                    "subtitled_path": None,
                    "formats": {"16:9": "/tmp/final/16x9/output.mp4"},
                }):
                    summary = pipeline.run()
                    assert summary["total_scenes"] == 2
                    assert summary["completed_scenes"] == 2
                    assert summary["assembly"]["master_path"] == "/tmp/master.mp4"

    def test_resume_delegates_to_run(self, mock_render_pipeline_deps):
        pipeline = RenderPipeline("ChannelA", "prod_001")

        with patch.object(pipeline, "run", return_value={"completed_scenes": 0}):
            result = pipeline.resume()
            assert result["completed_scenes"] == 0
            pipeline.run.assert_called_once()


class TestRenderPipelineRenderScenes:
    """RenderPipeline._render_scenes"""

    def test_skip_already_completed_scenes(self, mock_render_pipeline_deps, tmp_path):
        cp = mock_render_pipeline_deps["checkpoint"]
        cp.is_completed.return_value = True

        production_dir = tmp_path / "test_prod"
        production_dir.mkdir(parents=True, exist_ok=True)
        (production_dir / "render" / "scenes").mkdir(parents=True, exist_ok=True)

        pipeline = RenderPipeline("ChannelA", "prod_001")
        pipeline.production_dir = production_dir

        scenes = [{"scene_id": "scene_01", "scene_number": 1, "text": "Test"}]
        results = pipeline._render_scenes(scenes)
        assert len(results) == 1
        mock_render_pipeline_deps["render_scene"].assert_not_called()

    def test_handles_scene_render_failure(self, mock_render_pipeline_deps):
        mock_render_pipeline_deps["render_scene"].return_value = None

        pipeline = RenderPipeline("ChannelA", "prod_001")
        scenes = [{"scene_id": "scene_01", "scene_number": 1, "text": "Test"}]
        results = pipeline._render_scenes(scenes)
        assert len(results) == 0
