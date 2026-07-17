"""Tests for CharacterResolver — character SVG resolution with variant support.

Covers:
    - Default variant resolution
    - Specific variant resolution
    - Channel override priority (D-05)
    - Nonexistent character returns None
    - Nonexistent variant returns None
    - Missing metadata fallback to ``{name}.svg``
    - ``list_characters()`` scans both directories
    - Invalid channel names raise ValueError (T-10-05)
    - Corrupted metadata returns None (T-10-06)
"""

import json
from pathlib import Path

import pytest


# =========================================================================
# Helpers
# =========================================================================


def _create_character_dir(
    base: Path,
    name: str,
    *,
    metadata: dict | None = None,
    svg_files: dict[str, str] | None = None,
) -> Path:
    """Create a character directory under *base* with optional metadata and SVGs.

    Args:
        base: Parent ``characters/`` directory.
        name: Character directory name (e.g. ``"Anna"``).
        metadata: Dict to write as ``metadata.json``, or ``None`` to skip.
        svg_files: Dict mapping filenames to dummy SVG content.

    Returns:
        The created ``Path`` for the character directory.
    """
    char_dir = base / name
    char_dir.mkdir(parents=True, exist_ok=True)

    if metadata is not None:
        meta_path = char_dir / "metadata.json"
        meta_path.write_text(json.dumps(metadata), encoding="utf-8")

    if svg_files is not None:
        for filename, content in svg_files.items():
            (char_dir / filename).write_text(content, encoding="utf-8")

    return char_dir


# =========================================================================
# Tests
# =========================================================================


class TestCharacterResolver:
    """Test suite for CharacterResolver."""

    # -----------------------------------------------------------------
    # Basic resolution
    # -----------------------------------------------------------------

    def test_resolve_global_character_default_variant(self, tmp_path):
        """Resolve a global character with no variant → default_variant."""
        from agent_core.assets.characters import CharacterResolver

        base = tmp_path / "assets" / "consistent" / "global" / "characters"
        _create_character_dir(
            base,
            "Anna",
            metadata={
                "name": "Anna",
                "default_variant": "default",
                "variants": {"default": "default.svg", "happy": "happy.svg"},
                "tags": ["host"],
            },
            svg_files={"default.svg": "<svg/>", "happy.svg": "<svg/>"},
        )

        resolver = CharacterResolver("TestChannel")
        resolver.project_root = tmp_path

        result = resolver.resolve("Anna")
        assert result is not None
        assert result.name == "default.svg"
        assert str(result).endswith("Anna/default.svg")

    def test_resolve_character_specific_variant(self, tmp_path):
        """Resolve a character with an explicit variant name."""
        from agent_core.assets.characters import CharacterResolver

        base = tmp_path / "assets" / "consistent" / "global" / "characters"
        _create_character_dir(
            base,
            "Anna",
            metadata={
                "name": "Anna",
                "default_variant": "default",
                "variants": {"default": "default.svg", "happy": "happy.svg"},
                "tags": ["host"],
            },
            svg_files={"default.svg": "<svg/>", "happy.svg": "<svg/>"},
        )

        resolver = CharacterResolver("TestChannel")
        resolver.project_root = tmp_path

        result = resolver.resolve("Anna", "happy")
        assert result is not None
        assert result.name == "happy.svg"
        assert str(result).endswith("Anna/happy.svg")

    # -----------------------------------------------------------------
    # Channel override priority (D-05)
    # -----------------------------------------------------------------

    def test_channel_override_takes_priority(self, tmp_path):
        """Channel override path is returned before global path when both exist."""
        from agent_core.assets.characters import CharacterResolver

        # Global character
        global_base = tmp_path / "assets" / "consistent" / "global" / "characters"
        _create_character_dir(
            global_base,
            "Anna",
            metadata={
                "name": "Anna",
                "default_variant": "default",
                "variants": {"default": "default.svg"},
            },
            svg_files={"default.svg": "<!-- global -->"},
        )

        # Channel override (same character, different SVG content)
        channel_base = tmp_path / "channels" / "TestChannel" / "assets" / "characters"
        _create_character_dir(
            channel_base,
            "Anna",
            metadata={
                "name": "Anna",
                "default_variant": "default",
                "variants": {"default": "default.svg"},
            },
            svg_files={"default.svg": "<!-- channel override -->"},
        )

        resolver = CharacterResolver("TestChannel")
        resolver.project_root = tmp_path

        result = resolver.resolve("Anna")
        assert result is not None
        # Result should be in the channel override path, not global
        assert "channels/TestChannel" in str(result)
        assert result.name == "default.svg"

    # -----------------------------------------------------------------
    # Nonexistent / missing
    # -----------------------------------------------------------------

    def test_resolve_nonexistent_character_returns_none(self, tmp_path):
        """Resolving a character that doesn't exist anywhere returns None."""
        from agent_core.assets.characters import CharacterResolver

        resolver = CharacterResolver("TestChannel")
        resolver.project_root = tmp_path

        result = resolver.resolve("NonExistent")
        assert result is None

    def test_resolve_nonexistent_variant_returns_none(self, tmp_path):
        """Requesting a variant not in metadata returns None."""
        from agent_core.assets.characters import CharacterResolver

        base = tmp_path / "assets" / "consistent" / "global" / "characters"
        _create_character_dir(
            base,
            "Anna",
            metadata={
                "name": "Anna",
                "default_variant": "default",
                "variants": {"default": "default.svg"},
            },
            svg_files={"default.svg": "<svg/>"},
        )

        resolver = CharacterResolver("TestChannel")
        resolver.project_root = tmp_path

        result = resolver.resolve("Anna", "nonexistent")
        assert result is None

    # -----------------------------------------------------------------
    # Fallback behavior
    # -----------------------------------------------------------------

    def test_resolve_variant_falls_back_to_filename(self, tmp_path):
        """When variant not in variants dict, try {variant_name}.svg as filename."""
        from agent_core.assets.characters import CharacterResolver

        base = tmp_path / "assets" / "consistent" / "global" / "characters"
        char_dir = _create_character_dir(
            base,
            "Anna",
            metadata={
                "name": "Anna",
                "default_variant": "default",
                "variants": {"default": "default.svg"},
            },
            svg_files={"default.svg": "<svg/>"},
        )

        resolver = CharacterResolver("TestChannel")
        resolver.project_root = tmp_path

        # Request a variant not in the variants dict — should fall back to
        # {variant_name}.svg on disk. Since no such file exists → None.
        result = resolver.resolve("Anna", "custom")
        assert result is None

        # Now create the fallback file and try again
        (char_dir / "custom.svg").write_text("<svg/>", encoding="utf-8")
        result = resolver.resolve("Anna", "custom")
        assert result is not None
        assert result.name == "custom.svg"

    def test_resolve_without_metadata_falls_back_to_name_svg(self, tmp_path):
        """Characters without metadata.json fall back to ``{name}.svg``."""
        from agent_core.assets.characters import CharacterResolver

        base = tmp_path / "assets" / "consistent" / "global" / "characters"
        char_dir = _create_character_dir(
            base, "Bob", svg_files={"Bob.svg": "<svg/>"}
        )

        resolver = CharacterResolver("TestChannel")
        resolver.project_root = tmp_path

        result = resolver.resolve("Bob")
        assert result is not None
        assert result.name == "Bob.svg"
        assert str(result).endswith("Bob/Bob.svg")

    # -----------------------------------------------------------------
    # list_characters
    # -----------------------------------------------------------------

    def test_list_characters_scans_both_directories(self, tmp_path):
        """list_characters() returns entries from both global and channel dirs."""
        from agent_core.assets.characters import CharacterResolver

        # Character in global directory
        global_base = tmp_path / "assets" / "consistent" / "global" / "characters"
        _create_character_dir(
            global_base,
            "Anna",
            metadata={
                "name": "Anna",
                "default_variant": "default",
                "variants": {"default": "default.svg"},
            },
        )

        # Different character in channel override directory
        channel_base = tmp_path / "channels" / "TestChannel" / "assets" / "characters"
        _create_character_dir(
            channel_base,
            "Bob",
            metadata={
                "name": "Bob",
                "default_variant": "default",
                "variants": {"default": "default.svg"},
            },
        )

        resolver = CharacterResolver("TestChannel")
        resolver.project_root = tmp_path

        chars = resolver.list_characters()
        names = [c["name"] for c in chars]
        assert "Anna" in names
        assert "Bob" in names

    def test_list_characters_empty_when_no_dirs(self, tmp_path):
        """list_characters() returns [] when no character directories exist."""
        from agent_core.assets.characters import CharacterResolver

        resolver = CharacterResolver("TestChannel")
        resolver.project_root = tmp_path

        assert resolver.list_characters() == []

    def test_list_characters_skips_corrupted_dirs(self, tmp_path):
        """list_characters() skips entries with unreadable metadata."""
        from agent_core.assets.characters import CharacterResolver

        base = tmp_path / "assets" / "consistent" / "global" / "characters"
        # Valid character
        _create_character_dir(
            base,
            "Anna",
            metadata={
                "name": "Anna",
                "default_variant": "default",
                "variants": {"default": "default.svg"},
            },
        )
        # Corrupted metadata (not valid JSON)
        bad_dir = base / "BadChar"
        bad_dir.mkdir()
        (bad_dir / "metadata.json").write_text("not json", encoding="utf-8")

        resolver = CharacterResolver("TestChannel")
        resolver.project_root = tmp_path

        chars = resolver.list_characters()
        names = [c["name"] for c in chars]
        assert "Anna" in names
        assert "BadChar" not in names

    # -----------------------------------------------------------------
    # Invalid channel validation (T-10-05)
    # -----------------------------------------------------------------

    def test_invalid_channel_name_raises_value_error(self, tmp_path):
        """Channel names with path traversal characters raise ValueError."""
        from agent_core.assets.characters import CharacterResolver

        with pytest.raises(ValueError, match="Invalid channel name"):
            CharacterResolver("../evil")

        with pytest.raises(ValueError, match="Invalid channel name"):
            CharacterResolver("channel/name")

        with pytest.raises(ValueError, match="Invalid channel name"):
            CharacterResolver("channel.name")

    def test_validate_channel_static_method(self, tmp_path):
        """_validate_channel static method rejects bad names and accepts good ones."""
        from agent_core.assets.characters import CharacterResolver

        # Valid names
        CharacterResolver._validate_channel("TestChannel")
        CharacterResolver._validate_channel("channel-42")
        CharacterResolver._validate_channel("channel_name")

        # Invalid names
        with pytest.raises(ValueError, match="Invalid channel name"):
            CharacterResolver._validate_channel("../evil")
        with pytest.raises(ValueError, match="Invalid channel name"):
            CharacterResolver._validate_channel("channel/name")

    # -----------------------------------------------------------------
    # Corrupted metadata (T-10-06)
    # -----------------------------------------------------------------

    def test_corrupted_metadata_returns_none(self, tmp_path):
        """Corrupted metadata.json returns None instead of crashing."""
        from agent_core.assets.characters import CharacterResolver

        base = tmp_path / "assets" / "consistent" / "global" / "characters"
        char_dir = _create_character_dir(base, "Anna")
        # Write invalid JSON to metadata.json
        (char_dir / "metadata.json").write_text(
            "{invalid json content}", encoding="utf-8"
        )

        resolver = CharacterResolver("TestChannel")
        resolver.project_root = tmp_path

        # Should not raise — returns None
        result = resolver.resolve("Anna")
        assert result is None
