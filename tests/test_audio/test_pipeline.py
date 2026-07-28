"""
Integration tests for the AudioPipeline orchestrator.

Uses mocks to replace TTS, alignment, and script splitting dependencies
so that pipeline logic (checkpoint skipping, TTS failure handling, manifest
tracking) can be tested without external services or model downloads.
"""

from pathlib import Path

import pytest


class TestAudioPipelineInit:
    """Tests for AudioPipeline initialisation."""

    def test_pipeline_init(self):
        """Verify AudioPipeline init with a valid channel name (no filesystem)."""
        from agent_core.audio.pipeline import AudioPipeline

        # This will raise if channel validation fails, but won't actually
        # touch the filesystem for script loading (that happens at run()).
        with pytest.raises(ValueError, match="Invalid channel name"):
            AudioPipeline("Invalid@Channel!", "prod_001")


class TestAudioPipelineRun:
    """Tests for AudioPipeline.run()."""

    def test_pipeline_script_not_found(self, tmp_path, monkeypatch):
        """No script.json or script.txt → raises FileNotFoundError."""
        from agent_core.audio.pipeline import AudioPipeline

        # Patch _project_root to point at tmp_path so production_dir is empty
        import agent_core.audio.pipeline as pipeline_mod

        monkeypatch.setattr(
            pipeline_mod,
            "_project_root",
            lambda: tmp_path,
        )

        pipeline = AudioPipeline("TestChannel", "prod_001")
        with pytest.raises(FileNotFoundError, match="No script.json or script.txt"):
            pipeline.run()

    def test_pipeline_run_scene_processing(self, tmp_path, mocker, monkeypatch):
        """Mock TTS, aligner, splitter — verify output dict keys."""
        import agent_core.audio.pipeline as pipeline_mod

        # Patch project root to tmp_path
        monkeypatch.setattr(pipeline_mod, "_project_root", lambda: tmp_path)

        # Create a minimal script
        script_dir = tmp_path / "channels" / "TestChannel" / "active_production" / "prod_001"
        script_dir.mkdir(parents=True)
        script_file = script_dir / "script.json"
        script_file.write_text(
            '{"scenes": [{"scene_id": "scene_01", "scene_number": 1, "text": "Hello world."}]}',
            encoding="utf-8",
        )

        # Mock TTS FallbackChain.generate to return a fake TTSResult
        mock_audio_file = script_dir / "temp_audio.wav"
        mock_audio_file.write_text("fake audio")
        mock_tts_result = mocker.MagicMock(
            audio_path=str(mock_audio_file),
            duration_seconds=1.0,
            format="wav",
        )
        mocker.patch(
            "agent_core.audio.pipeline.FallbackChain.generate",
            return_value=mock_tts_result,
        )

        # Mock force_align_scene to return known alignment
        mock_alignment = [
            {"word": "Hello", "start": 0.0, "end": 0.3, "probability": 0.95},
            {"word": "world", "start": 0.35, "end": 0.6, "probability": 0.97},
        ]
        mocker.patch(
            "agent_core.audio.pipeline.force_align_scene",
            return_value=mock_alignment,
        )

        # Mock generate_subtitle_files to return paths
        mocker.patch(
            "agent_core.audio.pipeline.generate_subtitle_files",
            return_value={
                "srt": str(script_dir / "scene_01_subtitles.srt"),
                "vtt": str(script_dir / "scene_01_subtitles.vtt"),
            },
        )

        # Prevent CheckpointManager from creating directories in real data/ dir
        mocker.patch(
            "agent_core.audio.pipeline.CheckpointManager.is_completed",
            return_value=False,
        )
        mocker.patch(
            "agent_core.audio.pipeline.CheckpointManager.save_checkpoint",
            return_value=None,
        )

        from agent_core.audio.pipeline import AudioPipeline

        pipeline = AudioPipeline("TestChannel", "prod_001")
        summary = pipeline.run()

        assert summary["channel"] == "TestChannel"
        assert summary["production_id"] == "prod_001"
        assert summary["total_scenes"] == 1
        assert summary["completed_scenes"] == 1
        assert len(summary["scenes"]) == 1
        assert summary["scenes"][0]["scene_id"] == "scene_01"
        assert summary["scenes"][0]["status"] == "completed"
        assert "temp_manifest_path" in summary

    def test_pipeline_checkpoint_skips_completed(self, tmp_path, mocker, monkeypatch):
        """Checkpoint.is_completed returns True for scene_01 — verify it's skipped."""
        import agent_core.audio.pipeline as pipeline_mod

        monkeypatch.setattr(pipeline_mod, "_project_root", lambda: tmp_path)

        script_dir = tmp_path / "channels" / "TestChannel" / "active_production" / "prod_001"
        script_dir.mkdir(parents=True)
        script_file = script_dir / "script.json"
        script_file.write_text(
            '{"scenes": [{"scene_id": "scene_01", "scene_number": 1, "text": "Hello."}, {"scene_id": "scene_02", "scene_number": 2, "text": "World."}]}',
            encoding="utf-8",
        )

        # Mock is_completed to return True for scene_01, False for others
        def _mock_is_completed(self_cp, stage, pipeline_id, scene_id=None):
            if scene_id == "scene_01":
                return True
            return False

        monkeypatch.setattr(
            pipeline_mod.CheckpointManager,
            "is_completed",
            _mock_is_completed,
        )

        # Mock TTS to return a result
        mock_audio = script_dir / "temp.wav"
        mock_audio.write_text("x")
        mock_tts = mocker.MagicMock(
            audio_path=str(mock_audio),
            duration_seconds=1.0,
            format="wav",
        )
        mocker.patch(
            "agent_core.audio.pipeline.FallbackChain.generate",
            return_value=mock_tts,
        )
        mocker.patch(
            "agent_core.audio.pipeline.force_align_scene",
            return_value=[],
        )
        mocker.patch(
            "agent_core.audio.pipeline.generate_subtitle_files",
            return_value={"srt": "", "vtt": ""},
        )

        from agent_core.audio.pipeline import AudioPipeline

        pipeline = AudioPipeline("TestChannel", "prod_001")
        summary = pipeline.run()

        # scene_01 was skipped via checkpoint, only scene_02 was processed
        assert summary["total_scenes"] == 2
        assert summary["completed_scenes"] == 1
        assert len(summary["scenes"]) == 1
        assert summary["scenes"][0]["scene_id"] == "scene_02"

    def test_pipeline_manifest_tracks_all_assets(self, tmp_path, mocker, monkeypatch):
        """Verify manifest has all assets after pipeline run."""
        import agent_core.audio.pipeline as pipeline_mod

        monkeypatch.setattr(pipeline_mod, "_project_root", lambda: tmp_path)

        script_dir = tmp_path / "channels" / "TestChannel" / "active_production" / "prod_001"
        script_dir.mkdir(parents=True)
        script_file = script_dir / "script.json"
        script_file.write_text(
            '{"scenes": [{"scene_id": "scene_01", "scene_number": 1, "text": "Hello."}]}',
            encoding="utf-8",
        )

        mock_audio = script_dir / "temp.wav"
        mock_audio.write_text("x")
        mock_tts_result = mocker.MagicMock(
            audio_path=str(mock_audio),
            duration_seconds=1.0,
            format="wav",
        )
        mocker.patch(
            "agent_core.audio.pipeline.FallbackChain.generate",
            return_value=mock_tts_result,
        )
        mocker.patch(
            "agent_core.audio.pipeline.force_align_scene",
            return_value=[],
        )
        mocker.patch(
            "agent_core.audio.pipeline.generate_subtitle_files",
            return_value={"srt": "", "vtt": ""},
        )
        mocker.patch(
            "agent_core.audio.pipeline.CheckpointManager.is_completed",
            return_value=False,
        )

        from agent_core.audio.pipeline import AudioPipeline

        pipeline = AudioPipeline("TestChannel", "prod_001")
        summary = pipeline.run()

        # scene_02 failed, only 2 scenes completed
        assert summary["total_scenes"] == 3
        assert summary["completed_scenes"] == 2

    def test_pipeline_manifest_tracks_all_assets(self, tmp_path, mocker, monkeypatch):
        """Verify manifest has all assets after pipeline run."""
        import agent_core.audio.pipeline as pipeline_mod

        monkeypatch.setattr(pipeline_mod, "_project_root", lambda: tmp_path)

        script_dir = tmp_path / "channels" / "TestChannel" / "active_production" / "prod_001"
        script_dir.mkdir(parents=True)
        script_file = script_dir / "script.json"
        script_file.write_text(
            '{"scenes": [{"scene_id": "scene_01", "scene_number": 1, "text": "Hello."}]}',
            encoding="utf-8",
        )

        mock_audio = script_dir / "temp.wav"
        mock_audio.write_text("x")
        mock_tts_result = mocker.MagicMock(
            audio_path=str(mock_audio),
            duration_seconds=1.0,
            format="wav",
        )
        mocker.patch(
            "agent_core.audio.pipeline.FallbackChain.generate",
            return_value=mock_tts_result,
        )
        mocker.patch(
            "agent_core.audio.pipeline.force_align_scene",
            return_value=[],
        )
        mocker.patch(
            "agent_core.audio.pipeline.generate_subtitle_files",
            return_value={
                "srt": str(script_dir / "scene_01.srt"),
                "vtt": str(script_dir / "scene_01.vtt"),
            },
        )
        mocker.patch(
            "agent_core.audio.pipeline.CheckpointManager.is_completed",
            return_value=False,
        )
        mocker.patch(
            "agent_core.audio.pipeline.CheckpointManager.save_checkpoint",
            return_value=None,
        )

        from agent_core.audio.pipeline import AudioPipeline

        pipeline = AudioPipeline("TestChannel", "prod_001")
        pipeline.run()

        # Check manifest assets
        manifest_assets = pipeline.manifest.get_assets()
        assert len(manifest_assets) >= 2  # audio + srt + vtt = 3 minimum

    def test_run_audio_pipeline_convenience_function(self, mocker, monkeypatch, tmp_path):
        """Convenience function creates pipeline and runs it."""
        import agent_core.audio.pipeline as pipeline_mod

        monkeypatch.setattr(pipeline_mod, "_project_root", lambda: tmp_path)

        script_dir = tmp_path / "channels" / "TestChannel" / "active_production" / "prod_001"
        script_dir.mkdir(parents=True)
        script_file = script_dir / "script.json"
        script_file.write_text('{"scenes": []}', encoding="utf-8")

        from agent_core.audio.pipeline import run_audio_pipeline

        summary = run_audio_pipeline("TestChannel", "prod_001")
        assert summary["total_scenes"] == 0
        assert summary["completed_scenes"] == 0
