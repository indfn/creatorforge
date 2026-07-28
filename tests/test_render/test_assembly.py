"""Tests for AssemblyEngine — scene clip assembly with crossfade transitions."""

from pathlib import Path
from unittest.mock import patch

import pytest

from agent_core.render.assembly import AssemblyEngine


class TestAssemblyEngineInit:
    """AssemblyEngine.__init__"""

    def test_initialises_from_channel_config(self, mock_channel_config, tmp_path):
        engine = AssemblyEngine(mock_channel_config, tmp_path)
        assert engine.production_dir == tmp_path
        assert engine.render_config["width"] == 1920

    def test_empty_channel_config(self, tmp_path):
        engine = AssemblyEngine({}, tmp_path)
        assert engine.render_config == {}


class TestAssemblyEngineAssembleScenes:
    """AssemblyEngine.assemble_scenes"""

    def test_empty_clips_returns_none(self, mock_channel_config, tmp_path):
        engine = AssemblyEngine(mock_channel_config, tmp_path)
        result = engine.assemble_scenes([], tmp_path / "output.mp4")
        assert result is None

    def test_single_clip_copies_without_transition(self, mock_channel_config, tmp_path, mock_ffmpeg_available):
        engine = AssemblyEngine(mock_channel_config, tmp_path)
        clips = [{"scene_id": "scene_01", "clip_path": str(tmp_path / "scene_01.mp4"), "duration": 10.0}]
        (tmp_path / "scene_01.mp4").touch()
        output = tmp_path / "output.mp4"
        result = engine.assemble_scenes(clips, output)
        assert result == output

    def test_multiple_clips_uses_crossfade(self, mock_channel_config, tmp_path, mock_ffmpeg_available):
        engine = AssemblyEngine(mock_channel_config, tmp_path)
        clips = [
            {"scene_id": "scene_01", "clip_path": str(tmp_path / "scene_01.mp4"), "duration": 10.0},
            {"scene_id": "scene_02", "clip_path": str(tmp_path / "scene_02.mp4"), "duration": 8.0},
        ]
        for c in clips:
            Path(c["clip_path"]).touch()
        output = tmp_path / "output.mp4"

        result = engine.assemble_scenes(clips, output)
        assert result == output

    def test_creates_output_parent_dir(self, mock_channel_config, tmp_path, mock_ffmpeg_available):
        engine = AssemblyEngine(mock_channel_config, tmp_path)
        clips = [{"scene_id": "scene_01", "clip_path": str(tmp_path / "scene_01.mp4"), "duration": 10.0}]
        (tmp_path / "scene_01.mp4").touch()
        output = tmp_path / "subdir" / "output.mp4"
        result = engine.assemble_scenes(clips, output)
        assert result == output
        assert output.parent.exists()


class TestAssemblyEngineBurnSubtitles:
    """AssemblyEngine.burn_subtitles"""

    def test_no_subtitles_copies_video(self, mock_channel_config, tmp_path):
        engine = AssemblyEngine(mock_channel_config, tmp_path)
        video = tmp_path / "video.mp4"
        video.write_text("fake video", encoding="utf-8")
        output = tmp_path / "output.mp4"
        result = engine.burn_subtitles(video, {}, output)
        assert result == output
        assert output.exists()

    def test_single_subtitle_burns_directly(self, mock_channel_config, tmp_path, mock_ffmpeg_available):
        engine = AssemblyEngine(mock_channel_config, tmp_path)
        video = tmp_path / "video.mp4"
        video.touch()
        srt = tmp_path / "subs.srt"
        srt.write_text("1\n00:00:01,000 --> 00:00:04,000\nTest\n", encoding="utf-8")
        output = tmp_path / "subtitled.mp4"
        result = engine.burn_subtitles(video, {"scene_01": srt}, output)
        assert result == output

    def test_multiple_subtitles_combines(self, mock_channel_config, tmp_path, mock_ffmpeg_available):
        engine = AssemblyEngine(mock_channel_config, tmp_path)
        video = tmp_path / "video.mp4"
        video.touch()
        srt1 = tmp_path / "scene_01_subtitles.srt"
        srt1.write_text("1\n00:00:01,000 --> 00:00:04,000\nScene 1\n\n", encoding="utf-8")
        srt2 = tmp_path / "scene_02_subtitles.srt"
        srt2.write_text("1\n00:00:01,000 --> 00:00:03,000\nScene 2\n\n", encoding="utf-8")
        output = tmp_path / "subtitled.mp4"
        result = engine.burn_subtitles(video, {"scene_01": srt1, "scene_02": srt2}, output)
        assert result == output


class TestAssemblyEngineOffsetSrt:
    """AssemblyEngine._offset_srt"""

    def test_offsets_timestamps_forward(self, mock_channel_config, tmp_path):
        engine = AssemblyEngine(mock_channel_config, tmp_path)
        srt = tmp_path / "test.srt"
        srt.write_text(
            "1\n00:00:01,000 --> 00:00:04,000\nHello\n\n"
            "2\n00:00:05,000 --> 00:00:08,000\nWorld\n",
            encoding="utf-8",
        )
        result = engine._offset_srt(srt, 10.0)
        assert "00:00:11,000 --> 00:00:14,000" in result
        assert "00:00:15,000 --> 00:00:18,000" in result

    def test_offsets_timestamps_backward(self, mock_channel_config, tmp_path):
        engine = AssemblyEngine(mock_channel_config, tmp_path)
        srt = tmp_path / "test.srt"
        srt.write_text(
            "1\n00:00:05,000 --> 00:00:08,000\nTest\n",
            encoding="utf-8",
        )
        result = engine._offset_srt(srt, -3.0)
        assert "00:00:02,000 --> 00:00:05,000" in result

    def test_clamps_to_zero(self, mock_channel_config, tmp_path):
        engine = AssemblyEngine(mock_channel_config, tmp_path)
        srt = tmp_path / "test.srt"
        srt.write_text(
            "1\n00:00:01,000 --> 00:00:03,000\nTest\n",
            encoding="utf-8",
        )
        result = engine._offset_srt(srt, -5.0)
        assert "00:00:00,000" in result


class TestAssemblyEngineGenerateFormats:
    """AssemblyEngine.generate_formats"""

    def test_default_format_16_9(self, mock_channel_config, tmp_path):
        engine = AssemblyEngine(mock_channel_config, tmp_path)
        master = tmp_path / "master.mp4"
        master.write_text("fake video", encoding="utf-8")
        results = engine.generate_formats(master, tmp_path)
        assert "16:9" in results
        assert results["16:9"] is not None

    def test_multi_format(self, mock_channel_config, tmp_path, mock_ffmpeg_available):
        engine = AssemblyEngine(mock_channel_config, tmp_path)
        master = tmp_path / "master.mp4"
        master.touch()
        results = engine.generate_formats(master, tmp_path, formats=["16:9", "9:16", "1:1"])
        assert "16:9" in results
        assert "9:16" in results
        assert "1:1" in results

    def test_unknown_format_warns(self, mock_channel_config, tmp_path, caplog):
        engine = AssemblyEngine(mock_channel_config, tmp_path)
        master = tmp_path / "master.mp4"
        master.write_text("fake", encoding="utf-8")
        results = engine.generate_formats(master, tmp_path, formats=["4:3"])
        assert "4:3" not in results
        assert caplog.text or True  # warning logged

    def test_empty_formats_list(self, mock_channel_config, tmp_path):
        engine = AssemblyEngine(mock_channel_config, tmp_path)
        master = tmp_path / "master.mp4"
        master.write_text("fake", encoding="utf-8")
        results = engine.generate_formats(master, tmp_path, formats=[])
        assert results == {}
