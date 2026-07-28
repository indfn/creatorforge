"""Fixtures for render pipeline tests."""

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture
def mock_channel_config() -> dict[str, Any]:
    return {
        "render": {
            "width": 1920,
            "height": 1080,
            "fps": 30,
            "transition_duration": 0.5,
            "output_formats": ["16:9", "9:16"],
            "video_codec": "libx264",
            "preset": "medium",
            "crf": 23,
        },
    }


@pytest.fixture
def mock_channel_config_no_render() -> dict[str, Any]:
    return {"name": "ChannelA"}


@pytest.fixture
def mock_scene_clips() -> list[dict]:
    return [
        {"scene_id": "scene_01", "clip_path": "/tmp/scene_01.mp4", "duration": 10.0},
        {"scene_id": "scene_02", "clip_path": "/tmp/scene_02.mp4", "duration": 8.0},
        {"scene_id": "scene_03", "clip_path": "/tmp/scene_03.mp4", "duration": 12.0},
    ]


@pytest.fixture
def mock_single_scene_clip() -> list[dict]:
    return [
        {"scene_id": "scene_01", "clip_path": "/tmp/scene_01.mp4", "duration": 10.0},
    ]


@pytest.fixture
def mock_scenes_data() -> list[dict]:
    return [
        {"scene_id": "scene_01", "scene_number": 1, "text": "Welcome to this video."},
        {"scene_id": "scene_02", "scene_number": 2, "text": "Let me explain the concept."},
        {"scene_id": "scene_03", "scene_number": 3, "text": "Here is the key insight."},
    ]


@pytest.fixture
def mock_subtitle_paths(tmp_path) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for i in range(1, 4):
        scene_id = f"scene_{i:02d}"
        srt = tmp_path / f"{scene_id}_subtitles.srt"
        srt.write_text(
            "1\n00:00:01,000 --> 00:00:04,000\nTest subtitle for scene\n\n",
            encoding="utf-8",
        )
        paths[scene_id] = srt
    return paths


@pytest.fixture
def mock_ffmpeg_available():
    """Patches subprocess.run so ffmpeg commands don't execute for real."""
    with patch("agent_core.render.ffmpeg.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = b"{}"
        mock_run.return_value.stderr = b""
        yield mock_run


@pytest.fixture
def mock_playwright():
    """No-op fixture — mocking handled in individual tests."""
    yield


@pytest.fixture
def mock_render_pipeline_deps():
    """Mock all external deps for RenderPipeline tests."""
    with patch("agent_core.render.pipeline._load_channel_config") as mock_cfg:
        mock_cfg.return_value = {
            "render": {
                "width": 1920,
                "height": 1080,
                "fps": 30,
                "transition_duration": 0.5,
                "output_formats": ["16:9"],
            },
        }
        with patch("agent_core.render.pipeline.CheckpointManager") as mock_cp:
            mock_cp_instance = MagicMock()
            mock_cp.return_value = mock_cp_instance
            mock_cp_instance.is_completed.return_value = False
            with patch("agent_core.render.scene.render_scene") as mock_rs:
                mock_rs.return_value = Path("/tmp/rendered/scene_01.mp4")
                yield {
                    "channel_config": mock_cfg,
                    "checkpoint": mock_cp_instance,
                    "render_scene": mock_rs,
                }
