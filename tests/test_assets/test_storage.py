"""
Tests for asset storage helpers — path resolution, content hashing, naming.

Covers:
    - compute_content_hash: 8 char, deterministic, collision-resistant
    - build_asset_filename: with/without scene_id
    - consistent_asset_path: global vs channel override resolution
    - channel validation: invalid names raise ValueError
    - temp_asset_dir: correct pattern
    - asset_metadata_sidecar_path: .meta.json replacement
"""

from pathlib import Path

import pytest


class TestComputeContentHash:
    """Tests for content hash computation (D-15)."""

    def test_returns_8_chars(self):
        """compute_content_hash returns exactly 8 hex characters."""
        from agent_core.assets.storage import compute_content_hash

        result = compute_content_hash("https://example.com/v.mp4")
        assert len(result) == 8
        # Verify it's hex
        int(result, 16)

    def test_deterministic(self):
        """Same URL always produces the same hash."""
        from agent_core.assets.storage import compute_content_hash

        url = "https://example.com/video.mp4"
        assert compute_content_hash(url) == compute_content_hash(url)

    def test_different_urls_different_hashes(self):
        """Different URLs produce different hashes (collision resistance)."""
        from agent_core.assets.storage import compute_content_hash

        h1 = compute_content_hash("https://example.com/a.mp4")
        h2 = compute_content_hash("https://example.com/b.mp4")
        assert h1 != h2


class TestBuildAssetFilename:
    """Tests for asset filename construction (D-13, D-16)."""

    def test_with_scene_id(self):
        """Filename includes scene_id when provided."""
        from agent_core.assets.storage import build_asset_filename

        name = build_asset_filename("broll", "abc12345", "scene_03", "mp4")
        assert name == "broll_abc12345_scene_03.mp4"

    def test_without_scene_id(self):
        """Filename omits scene_id when not provided."""
        from agent_core.assets.storage import build_asset_filename

        name = build_asset_filename("image", "abc12345", extension="jpg")
        assert name == "image_abc12345.jpg"

    def test_default_extension_is_mp4(self):
        """Default extension is mp4 when not specified."""
        from agent_core.assets.storage import build_asset_filename

        name = build_asset_filename("broll", "abc12345")
        assert name == "broll_abc12345.mp4"


class TestConsistentAssetPath:
    """Tests for consistent asset path resolution (D-06)."""

    def test_global_path(self):
        """Without channel, path resolves to assets/consistent/global/."""
        from agent_core.assets.storage import consistent_asset_path

        path = consistent_asset_path("broll", "test.mp4")
        assert str(path).endswith("assets/consistent/global/broll/test.mp4")

    def test_channel_override_path(self):
        """With channel, path resolves to channels/{Name}/assets/."""
        from agent_core.assets.storage import consistent_asset_path

        path = consistent_asset_path("broll", "test.mp4", "ChannelA")
        assert str(path).endswith("channels/ChannelA/assets/broll/test.mp4")

    def test_image_type_maps_to_images_dir(self):
        """Image asset type uses 'images' directory."""
        from agent_core.assets.storage import consistent_asset_path

        path = consistent_asset_path("image", "pic.jpg")
        assert str(path).endswith("images/pic.jpg")

    def test_sfx_type_maps_to_sfx_dir(self):
        """SFX asset type uses 'sfx' directory."""
        from agent_core.assets.storage import consistent_asset_path

        path = consistent_asset_path("sfx", "sound.mp3")
        assert str(path).endswith("sfx/sound.mp3")

    def test_character_type_maps_to_characters_dir(self):
        """Character asset type uses 'characters' directory."""
        from agent_core.assets.storage import consistent_asset_path

        path = consistent_asset_path("character", "hero.svg")
        assert str(path).endswith("characters/hero.svg")

    def test_unknown_type_uses_default_misc_dir(self):
        """Unknown asset type falls back to 'misc' directory."""
        from agent_core.assets.storage import consistent_asset_path

        path = consistent_asset_path("unknown_type", "file.bin")
        assert str(path).endswith("misc/file.bin")

    def test_invalid_channel_raises_value_error(self):
        """Channel name with invalid characters raises ValueError."""
        from agent_core.assets.storage import consistent_asset_path

        with pytest.raises(ValueError, match="Invalid channel name"):
            consistent_asset_path("broll", "test.mp4", "bad/../path")

    def test_channel_with_special_chars_raises(self):
        """Channel with special characters (slashes, dots) raises ValueError."""
        from agent_core.assets.storage import consistent_asset_path

        with pytest.raises(ValueError, match="Invalid channel name"):
            consistent_asset_path("broll", "test.mp4", "channel.name")

        with pytest.raises(ValueError, match="Invalid channel name"):
            consistent_asset_path("broll", "test.mp4", "channel/name")


class TestTempAssetDir:
    """Tests for temp asset directory resolution (D-07)."""

    def test_temp_asset_dir_pattern(self):
        """Temp dir resolves to channels/{Name}/active_production/{id}/assets."""
        from agent_core.assets.storage import temp_asset_dir

        path = temp_asset_dir("ChannelA", "prod_001")
        assert str(path).endswith("channels/ChannelA/active_production/prod_001/assets")

    def test_temp_asset_dir_invalid_channel_raises(self):
        """Invalid channel name raises ValueError."""
        from agent_core.assets.storage import temp_asset_dir

        with pytest.raises(ValueError, match="Invalid channel name"):
            temp_asset_dir("invalid/path", "prod_001")


class TestAssetMetadataSidecar:
    """Tests for metadata sidecar path generation (D-09)."""

    def test_sidecar_path_extension(self):
        """Sidecar path replaces extension with .meta.json."""
        from agent_core.assets.storage import asset_metadata_sidecar_path

        result = asset_metadata_sidecar_path(Path("/path/to/video.mp4"))
        assert result == Path("/path/to/video.meta.json")

    def test_sidecar_path_with_multiple_extensions(self):
        """Sidecar replaces the last extension only (stdlib Path.with_suffix behavior)."""
        from agent_core.assets.storage import asset_metadata_sidecar_path

        result = asset_metadata_sidecar_path(Path("/path/to/archive.tar.gz"))
        # Path.with_suffix replaces only the last suffix
        assert result == Path("/path/to/archive.tar.meta.json")

    def test_sidecar_path_relative(self):
        """Sidecar works with relative paths too."""
        from agent_core.assets.storage import asset_metadata_sidecar_path

        result = asset_metadata_sidecar_path(Path("relative/path/file.mp4"))
        assert result == Path("relative/path/file.meta.json")
