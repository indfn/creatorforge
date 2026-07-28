"""Tests for FFmpegUtils."""

import json
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from agent_core.render.ffmpeg import FFmpegUtils


class TestFFmpegUtilsCheckAvailable:
    """FFmpegUtils.check_available"""

    def test_ffmpeg_available(self):
        with patch("agent_core.render.ffmpeg.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            assert FFmpegUtils.check_available() is True

    def test_ffmpeg_not_available(self):
        with patch("agent_core.render.ffmpeg.subprocess.run", side_effect=FileNotFoundError):
            assert FFmpegUtils.check_available() is False

    def test_ffmpeg_fails(self):
        with patch("agent_core.render.ffmpeg.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, [])
            assert FFmpegUtils.check_available() is False


class TestFFmpegUtilsRun:
    """FFmpegUtils.run"""

    def test_success(self):
        with patch("agent_core.render.ffmpeg.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            result = FFmpegUtils.run(["ffmpeg", "-version"])
            assert result is not None
            assert result.returncode == 0

    def test_failure_nonzero(self):
        with patch("agent_core.render.ffmpeg.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            mock_run.return_value.stderr = b"error"
            result = FFmpegUtils.run(["ffmpeg", "invalid"])
            assert result is None

    def test_timeout(self):
        with patch("agent_core.render.ffmpeg.subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 10)):
            result = FFmpegUtils.run(["ffmpeg", "-i", "input.mp4"], timeout=10)
            assert result is None

    def test_file_not_found(self):
        with patch("agent_core.render.ffmpeg.subprocess.run", side_effect=FileNotFoundError):
            result = FFmpegUtils.run(["ffmpeg"])
            assert result is None


class TestFFmpegUtilsVideoInfo:
    """FFmpegUtils.video_info"""

    def test_parse_success(self):
        fake_ffprobe = json.dumps({
            "format": {"duration": "30.5"},
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1920,
                    "height": 1080,
                    "r_frame_rate": "30000/1001",
                },
            ],
        })
        with patch("agent_core.render.ffmpeg.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = fake_ffprobe.encode()
            info = FFmpegUtils.video_info(Path("/tmp/test.mp4"))
            assert info["duration"] == 30.5
            assert info["width"] == 1920
            assert info["height"] == 1080
            assert info["codec"] == "h264"
            assert info["fps"] == pytest.approx(29.97, rel=0.1)

    def test_parse_failure_json(self):
        with patch("agent_core.render.ffmpeg.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = b"not json"
            info = FFmpegUtils.video_info(Path("/tmp/bad.mp4"))
            assert info == {}

    def test_no_video_stream(self):
        fake_ffprobe = json.dumps({
            "format": {"duration": "10.0"},
            "streams": [{"codec_type": "audio"}],
        })
        with patch("agent_core.render.ffmpeg.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = fake_ffprobe.encode()
            info = FFmpegUtils.video_info(Path("/tmp/audio_only.mp4"))
            assert "duration" in info
            assert "codec" not in info

    def test_file_not_found(self):
        with patch("agent_core.render.ffmpeg.subprocess.run", side_effect=FileNotFoundError):
            info = FFmpegUtils.video_info(Path("/tmp/nonexistent.mp4"))
            assert info == {}


class TestFFmpegUtilsSceneDuration:
    """FFmpegUtils.scene_duration"""

    def test_returns_duration(self):
        with patch.object(FFmpegUtils, "video_info", return_value={"duration": 15.5}):
            assert FFmpegUtils.scene_duration(Path("/tmp/test.mp4")) == 15.5

    def test_returns_zero_on_failure(self):
        with patch.object(FFmpegUtils, "video_info", return_value={}):
            assert FFmpegUtils.scene_duration(Path("/tmp/test.mp4")) == 0.0


class TestFFmpegUtilsSceneClipFromFrames:
    """FFmpegUtils.scene_clip_from_frames"""

    def test_success(self, tmp_path, mock_ffmpeg_available):
        frame_dir = tmp_path / "frames"
        frame_dir.mkdir()
        output = tmp_path / "scene.mp4"
        result = FFmpegUtils.scene_clip_from_frames(frame_dir, output, fps=30)
        assert result == output

    def test_creates_parent_dir(self, tmp_path, mock_ffmpeg_available):
        frame_dir = tmp_path / "frames"
        frame_dir.mkdir()
        output = tmp_path / "subdir" / "scene.mp4"
        result = FFmpegUtils.scene_clip_from_frames(frame_dir, output)
        assert result == output
        assert output.parent.exists()


class TestFFmpegUtilsConcatClips:
    """FFmpegUtils.concat_clips"""

    def test_concat_success(self, tmp_path, mock_ffmpeg_available):
        clips = [tmp_path / "clip1.mp4", tmp_path / "clip2.mp4"]
        for c in clips:
            c.touch()
        output = tmp_path / "concat.mp4"
        result = FFmpegUtils.concat_clips(clips, output)
        assert result == output

    def test_empty_clips_list(self, tmp_path):
        result = FFmpegUtils.concat_clips([], tmp_path / "out.mp4")
        assert result is None

    def test_single_clip(self, tmp_path, mock_ffmpeg_available):
        clip = tmp_path / "clip1.mp4"
        clip.touch()
        output = tmp_path / "output.mp4"
        result = FFmpegUtils.concat_clips([clip], output)
        assert result == output


class TestFFmpegUtilsBurnSubtitles:
    """FFmpegUtils.burn_subtitles"""

    def test_success(self, tmp_path, mock_ffmpeg_available):
        video = tmp_path / "video.mp4"
        video.touch()
        srt = tmp_path / "subs.srt"
        srt.write_text("1\n00:00:01,000 --> 00:00:04,000\nTest\n", encoding="utf-8")
        output = tmp_path / "subtitled.mp4"
        result = FFmpegUtils.burn_subtitles(video, srt, output)
        assert result == output


class TestFFmpegUtilsScaleCrop:
    """FFmpegUtils.scale_crop"""

    def test_success(self, tmp_path, mock_ffmpeg_available):
        video = tmp_path / "video.mp4"
        video.touch()
        output = tmp_path / "cropped.mp4"
        result = FFmpegUtils.scale_crop(video, output, 1080, 1920)
        assert result == output


class TestFFmpegUtilsCrossfadeAssembly:
    """FFmpegUtils.crossfade_assembly — the most complex method"""

    def test_empty_clips_returns_none(self, tmp_path):
        result = FFmpegUtils.crossfade_assembly([], tmp_path / "out.mp4")
        assert result is None

    def test_single_clip_uses_concat(self, tmp_path, mock_ffmpeg_available):
        clip = tmp_path / "clip.mp4"
        clip.touch()
        output = tmp_path / "out.mp4"
        result = FFmpegUtils.crossfade_assembly([clip], output)
        assert result == output

    def test_two_clips_builds_valid_filter(self, tmp_path, mock_ffmpeg_available):
        clip1 = tmp_path / "clip1.mp4"
        clip2 = tmp_path / "clip2.mp4"
        clip1.touch()
        clip2.touch()
        output = tmp_path / "out.mp4"

        with patch.object(FFmpegUtils, "scene_duration", return_value=10.0):
            with patch.object(FFmpegUtils, "run") as mock_run:
                mock_run.return_value.returncode = 0
                result = FFmpegUtils.crossfade_assembly([clip1, clip2], output, 0.5)
                assert result == output
                assert mock_run.call_count >= 1
                call_args = mock_run.call_args[0][0]
                cmd_str = " ".join(str(a) for a in call_args)
                assert "xfade" in cmd_str
                assert "acrossfade" in cmd_str
                assert "-filter_complex" in call_args
                fc_idx = call_args.index("-filter_complex") + 1
                filter_str = call_args[fc_idx]
                assert "[0:v][1:v]xfade" in filter_str.replace(" ", "")
                assert "[0:a][1:a]acrossfade" in filter_str.replace(" ", "")

    def test_three_clips_builds_valid_filter(self, tmp_path, mock_ffmpeg_available):
        clips = [tmp_path / f"clip{i}.mp4" for i in range(1, 4)]
        for c in clips:
            c.touch()
        output = tmp_path / "out.mp4"

        with patch.object(FFmpegUtils, "scene_duration", return_value=10.0):
            with patch.object(FFmpegUtils, "run") as mock_run:
                mock_run.return_value.returncode = 0
                result = FFmpegUtils.crossfade_assembly(clips, output, 0.5)
                assert result == output
                call_args = mock_run.call_args[0][0]
                fc_idx = call_args.index("-filter_complex") + 1
                filter_str = call_args[fc_idx]
                # Each clip pair should have an xfade
                assert "[0:v][1:v]xfade" in filter_str
                assert "[v0][2:v]xfade" in filter_str
                # Each audio pair should have acrossfade
                assert "[0:a][1:a]acrossfade" in filter_str
                assert "[a0][2:a]acrossfade" in filter_str
                # No stray labels appended without semicolons
                assert ";".strip() not in filter_str.split(";")[-1]

    def test_five_clips_builds_valid_filter(self, tmp_path, mock_ffmpeg_available):
        clips = [tmp_path / f"clip{i}.mp4" for i in range(1, 6)]
        for c in clips:
            c.touch()
        output = tmp_path / "out.mp4"

        with patch.object(FFmpegUtils, "scene_duration", return_value=10.0):
            with patch.object(FFmpegUtils, "run") as mock_run:
                mock_run.return_value.returncode = 0
                result = FFmpegUtils.crossfade_assembly(clips, output, 0.5)
                assert result == output
                call_args = mock_run.call_args[0][0]
                fc_idx = call_args.index("-filter_complex") + 1
                filter_str = call_args[fc_idx]
                segments = filter_str.split(";")
                assert len(segments) > 4  # 4 xfade + 4 acrossfade
                assert "-map" in call_args
                map_idx = call_args.index("-map") + 1
                assert "[v" in call_args[map_idx]
                assert "[a" in call_args[map_idx + 2]
