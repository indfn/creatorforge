"""
Tests for TempAssetManifest lifecycle and temp asset cleanup.

Covers:
    - Manifest initialisation (no file created until first add)
    - Add and get assets (all, by scene_id)
    - Persistence across reload (JSON read-back)
    - Cleanup (deletes files, handles missing files gracefully)
    - Unknown asset type warning
    - register_temp_cleanup returns callable handler
    - Cleanup manifest deletion
"""

from pathlib import Path

import pytest


class TestTempAssetManifest:
    """Tests for the TempAssetManifest class."""

    def test_manifest_init_creates_no_file(self, tmp_path):
        """Initialising a manifest doesn't create a file (no assets yet)."""
        from agent_core.audio.lifecycle import TempAssetManifest

        manifest = TempAssetManifest(tmp_path)
        assert not manifest.manifest_path.exists()
        assert manifest.assets == []

    def test_manifest_add_and_get(self, tmp_path):
        """Add 2 assets, get all, get by scene_id."""
        from agent_core.audio.lifecycle import TempAssetManifest

        manifest = TempAssetManifest(tmp_path)

        manifest.add("scene_01", str(tmp_path / "scene_01_audio.wav"), "audio")
        manifest.add("scene_01", str(tmp_path / "scene_01_subtitles.srt"), "srt")

        all_assets = manifest.get_assets()
        assert len(all_assets) == 2

        scene_assets = manifest.get_assets("scene_01")
        assert len(scene_assets) == 2

        other = manifest.get_assets("scene_99")
        assert len(other) == 0

    def test_manifest_persists_across_reload(self, tmp_path):
        """Create manifest, add, create new instance, verify assets loaded."""
        from agent_core.audio.lifecycle import TempAssetManifest

        # First instance
        m1 = TempAssetManifest(tmp_path)
        m1.add("scene_01", str(tmp_path / "audio.wav"), "audio")
        m1.add("scene_01", str(tmp_path / "subs.srt"), "srt")

        # Second instance pointing at the same dir
        m2 = TempAssetManifest(tmp_path)
        assert len(m2.assets) == 2
        assert m2.assets[0]["scene_id"] == "scene_01"
        assert m2.assets[1]["asset_type"] == "srt"

    def test_manifest_cleanup_deletes_files(self, tmp_path):
        """Create actual temp files, add to manifest, cleanup, verify deleted."""
        from agent_core.audio.lifecycle import TempAssetManifest

        # Create actual files
        audio_file = tmp_path / "audio.wav"
        audio_file.write_text("fake audio data")
        srt_file = tmp_path / "subs.srt"
        srt_file.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello")

        manifest = TempAssetManifest(tmp_path)
        manifest.add("scene_01", str(audio_file), "audio")
        manifest.add("scene_01", str(srt_file), "srt")

        assert audio_file.exists()
        assert srt_file.exists()

        deleted = manifest.cleanup()

        assert not audio_file.exists()
        assert not srt_file.exists()
        assert "audio.wav" in str(deleted[0])
        assert "subs.srt" in str(deleted[1])

    def test_manifest_cleanup_removes_manifest(self, tmp_path):
        """Verify manifest.json is deleted after cleanup."""
        from agent_core.audio.lifecycle import TempAssetManifest

        manifest = TempAssetManifest(tmp_path)
        manifest.add("scene_01", str(tmp_path / "audio.wav"), "audio")

        assert manifest.manifest_path.exists()
        manifest.cleanup()
        assert not manifest.manifest_path.exists()

    def test_manifest_cleanup_handles_missing_files(self, tmp_path):
        """Add file that doesn't exist, cleanup doesn't crash."""
        from agent_core.audio.lifecycle import TempAssetManifest

        manifest = TempAssetManifest(tmp_path)
        manifest.add("scene_01", str(tmp_path / "nonexistent.wav"), "audio")

        deleted = manifest.cleanup()
        assert len(deleted) >= 1  # manifest itself
        assert manifest.assets == []

    def test_manifest_empty_cleanup(self, tmp_path):
        """Cleanup with no assets still removes manifest if it exists."""
        from agent_core.audio.lifecycle import TempAssetManifest

        manifest = TempAssetManifest(tmp_path)
        # Force-save an empty manifest
        manifest._save()
        assert manifest.manifest_path.exists()

        deleted = manifest.cleanup()
        assert not manifest.manifest_path.exists()
        assert len(deleted) >= 1  # manifest was deleted

    def test_manifest_add_unknown_asset_type(self, tmp_path, caplog):
        """Warning logged but asset still added."""
        import logging

        from agent_core.audio.lifecycle import TempAssetManifest

        manifest = TempAssetManifest(tmp_path)
        caplog.set_level(logging.WARNING)

        manifest.add("scene_01", str(tmp_path / "unknown.xyz"), "unknown_type")

        # Warning should be logged
        assert any(
            "unknown asset type" in record.message.lower()
            for record in caplog.records
        )

        # Asset should still be in manifest
        assert len(manifest.assets) == 1
        assert manifest.assets[0]["asset_type"] == "unknown_type"

    def test_manifest_add_scene_assets_convenience(self, tmp_path):
        """add_scene_assets adds all 3-4 assets for a scene."""
        from agent_core.audio.lifecycle import TempAssetManifest

        manifest = TempAssetManifest(tmp_path)
        manifest.add_scene_assets(
            scene_id="scene_01",
            audio_path=str(tmp_path / "audio.wav"),
            srt_path=str(tmp_path / "subs.srt"),
            vtt_path=str(tmp_path / "subs.vtt"),
            alignment_path=str(tmp_path / "align.json"),
        )

        assert len(manifest.assets) == 4
        types = {a["asset_type"] for a in manifest.assets}
        assert types == {"audio", "srt", "vtt", "alignment_json"}

    def test_manifest_total_size(self, tmp_path):
        """total_size_bytes sums up file sizes."""
        from agent_core.audio.lifecycle import TempAssetManifest

        audio_file = tmp_path / "audio.wav"
        audio_file.write_text("x" * 1000)

        manifest = TempAssetManifest(tmp_path)
        manifest.add("scene_01", str(audio_file), "audio")

        assert manifest.total_size_bytes() == 1000

    def test_cleanup_deletes_only_manifest_listed_files(self, tmp_path):
        """Only files in manifest are deleted — other files remain."""
        from agent_core.audio.lifecycle import TempAssetManifest

        # Create files
        tracked_file = tmp_path / "tracked.wav"
        tracked_file.write_text("tracked")
        untracked_file = tmp_path / "untracked.txt"
        untracked_file.write_text("should remain")

        manifest = TempAssetManifest(tmp_path)
        manifest.add("scene_01", str(tracked_file), "audio")
        manifest.cleanup()

        assert not tracked_file.exists()
        assert untracked_file.exists()  # not deleted


class TestRegisterTempCleanup:
    """Tests for register_temp_cleanup."""

    def test_register_temp_cleanup_returns_handler(self, tmp_path, monkeypatch):
        """Verify returned callable."""
        from agent_core.audio.lifecycle import register_temp_cleanup, _production_dir

        # Patch _production_dir to use tmp_path
        monkeypatch.setattr(
            "agent_core.audio.lifecycle._production_dir",
            lambda c, p: tmp_path,
        )

        handler = register_temp_cleanup("TestChannel", "prod_001")
        assert callable(handler)

        # Calling the handler should not raise
        result = handler()
        assert result == 0  # no files to clean

    def test_register_temp_cleanup_cleanup_actual_files(self, tmp_path, monkeypatch):
        """Register cleanup with actual temp files."""
        from agent_core.audio.lifecycle import register_temp_cleanup

        audio_file = tmp_path / "test.wav"
        audio_file.write_text("data")

        # Create a manifest with the file
        from agent_core.audio.lifecycle import TempAssetManifest
        m = TempAssetManifest(tmp_path)
        m.add("scene_01", str(audio_file), "audio")

        monkeypatch.setattr(
            "agent_core.audio.lifecycle._production_dir",
            lambda c, p: tmp_path,
        )

        handler = register_temp_cleanup("TestChannel", "prod_001")
        result = handler()
        assert result >= 1  # at least the manifest
