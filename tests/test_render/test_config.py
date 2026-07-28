"""Tests for render config loading and defaults."""

from unittest.mock import patch

import pytest

from agent_core.render.pipeline import _merge_render_config, RenderPipeline


class TestMergeRenderConfig:
    """_merge_render_config"""

    def test_uses_defaults_when_no_render_section(self):
        merged = _merge_render_config({})
        assert merged["width"] == 1920
        assert merged["height"] == 1080
        assert merged["fps"] == 30
        assert merged["transition_duration"] == 0.5
        assert merged["output_formats"] == ["16:9"]
        assert merged["video_codec"] == "libx264"

    def test_overrides_defaults_with_channel_config(self):
        merged = _merge_render_config({
            "render": {"width": 3840, "fps": 60},
        })
        assert merged["width"] == 3840
        assert merged["fps"] == 60
        assert merged["height"] == 1080  # default preserved

    def test_partial_override_preserves_other_defaults(self):
        merged = _merge_render_config({
            "render": {"transition_duration": 1.0},
        })
        assert merged["transition_duration"] == 1.0
        assert merged["fps"] == 30  # default preserved

    def test_empty_render_section_uses_all_defaults(self):
        merged = _merge_render_config({"render": {}})
        assert merged["fps"] == 30
        assert merged["width"] == 1920


class TestRenderPipelineConfigValidation:
    """RenderPipeline render config integration"""

    def test_loads_config_from_channel(self):
        with patch("agent_core.render.pipeline._load_channel_config") as mock_cfg:
            mock_cfg.return_value = {
                "render": {"width": 1920, "height": 1080, "fps": 30},
            }
            pipeline = RenderPipeline("ChannelA", "test_prod")
            assert pipeline.render_config["width"] == 1920
            assert pipeline.render_config["fps"] == 30

    def test_fallback_defaults_on_missing_config(self):
        with patch("agent_core.render.pipeline._load_channel_config", return_value={}):
            pipeline = RenderPipeline("ChannelA", "test_prod")
            assert pipeline.render_config["width"] == 1920
            assert pipeline.render_config["fps"] == 30

    def test_render_config_in_assembly_engine(self):
        with patch("agent_core.render.pipeline._load_channel_config", return_value={
            "render": {"transition_duration": 2.0},
        }):
            pipeline = RenderPipeline("ChannelA", "test_prod")
            assert pipeline.assembly_engine.render_config["transition_duration"] == 2.0

    def test_pipeline_renders_with_custom_config(self):
        with patch("agent_core.render.pipeline._load_channel_config") as mock_cfg:
            mock_cfg.return_value = {
                "render": {"width": 1080, "height": 1920, "fps": 24},
            }
            pipeline = RenderPipeline("ChannelA", "test_prod")
            with patch.object(pipeline, "_load_scenes", return_value=[]):
                summary = pipeline.run()
                assert summary["total_scenes"] == 0
