"""
Tests for subtitle generation — SRT/VTT format spec compliance, word grouping, and edge cases.

Covers:
    - Timestamp formatting (SRT and VTT, clamping)
    - Word grouping (character limit, pause detection, edge cases)
    - SRT and VTT content generation (basic, empty)
    - File writing via ``generate_subtitle_files``
"""

from pathlib import Path

import pytest


# =========================================================================
# Timestamp formatting
# =========================================================================


class TestFormatTimestamp:
    """Tests for the _format_timestamp helper."""

    def test_format_timestamp_srt(self):
        """SRT format: HH:MM:SS,mmm"""
        from agent_core.audio.subtitles.generator import _format_timestamp

        # 1 hour, 23 minutes, 45.678 seconds
        result = _format_timestamp(3600 + 23 * 60 + 45.678, srt_format=True)
        assert result == "01:23:45,678"

    def test_format_timestamp_vtt(self):
        """VTT format: HH:MM:SS.mmm"""
        from agent_core.audio.subtitles.generator import _format_timestamp

        result = _format_timestamp(3661.5, srt_format=False)  # 1h 1m 1.5s
        assert result == "01:01:01.500"

    def test_format_timestamp_clamping_negative(self):
        """Negative seconds clamp to 0."""
        from agent_core.audio.subtitles.generator import _format_timestamp

        result = _format_timestamp(-5.0, srt_format=True)
        assert result == "00:00:00,000"

    def test_format_timestamp_zero(self):
        """Zero seconds."""
        from agent_core.audio.subtitles.generator import _format_timestamp

        assert _format_timestamp(0.0) == "00:00:00,000"

    def test_format_timestamp_subsecond(self):
        """Sub-second values."""
        from agent_core.audio.subtitles.generator import _format_timestamp

        assert _format_timestamp(0.123) == "00:00:00,123"


# =========================================================================
# Word grouping
# =========================================================================


class TestGroupWords:
    """Tests for _group_words."""

    def test_group_words_basic(self, sample_word_timestamps):
        """Simple word list — verify grouping into ≤42 char chunks."""
        from agent_core.audio.subtitles.generator import _group_words

        groups = _group_words(sample_word_timestamps)

        assert len(groups) >= 1
        for group in groups:
            chars = sum(len(w["word"]) for w in group) + (len(group) - 1)  # spaces
            assert chars <= 42, f"Group exceeds 42 chars: {chars}"

    def test_group_words_respects_pause(self):
        """A >500ms gap creates a new group."""
        from agent_core.audio.subtitles.generator import _group_words

        words = [
            {"word": "Hello", "start": 0.0, "end": 0.3},
            {"word": "world", "start": 0.35, "end": 0.6},
            {"word": "pause", "start": 2.0, "end": 2.3},  # 1.4s gap — new group
        ]

        groups = _group_words(words)
        assert len(groups) == 2
        assert len(groups[0]) == 2  # Hello world
        assert len(groups[1]) == 1  # pause

    def test_group_words_single_word(self):
        """Single word returns [[word]]."""
        from agent_core.audio.subtitles.generator import _group_words

        groups = _group_words([{"word": "Hello", "start": 0.0, "end": 0.5}])
        assert len(groups) == 1
        assert len(groups[0]) == 1

    def test_group_words_empty_input(self):
        """Empty input returns []."""
        from agent_core.audio.subtitles.generator import _group_words

        assert _group_words([]) == []


# =========================================================================
# SRT generation
# =========================================================================


class TestGenerateSRT:
    """Tests for generate_srt."""

    def test_generate_srt_basic(self, sample_word_timestamps):
        """Full SRT output format check."""
        from agent_core.audio.subtitles.generator import generate_srt

        content = generate_srt(sample_word_timestamps)

        assert content.startswith("1")
        assert "-->" in content
        assert "00:" in content  # timestamp prefix
        assert content.strip().endswith("now")  # last word

        # Count subtitle blocks (each block is 4 lines: index, time, text, blank)
        blocks = [b for b in content.split("\n\n") if b.strip()]
        assert len(blocks) >= 1

    def test_generate_srt_empty(self):
        """Empty input → empty string."""
        from agent_core.audio.subtitles.generator import generate_srt

        assert generate_srt([]) == ""


# =========================================================================
# VTT generation
# =========================================================================


class TestGenerateVTT:
    """Tests for generate_vtt."""

    def test_generate_vtt_basic(self, sample_word_timestamps):
        """Full VTT output format check."""
        from agent_core.audio.subtitles.generator import generate_vtt

        content = generate_vtt(sample_word_timestamps)

        assert content.startswith("WEBVTT")
        assert "-->" in content
        assert "00:" in content

    def test_generate_vtt_empty(self):
        """Empty input → 'WEBVTT\\n' (header only)."""
        from agent_core.audio.subtitles.generator import generate_vtt

        result = generate_vtt([])
        assert result.startswith("WEBVTT")
        assert len(result.strip().split("\n")) == 1  # just the header


# =========================================================================
# File writing
# =========================================================================


class TestGenerateSubtitleFiles:
    """Tests for generate_subtitle_files."""

    def test_generate_subtitle_files_writes_both(self, tmp_path, sample_word_timestamps):
        """Verify both .srt and .vtt files written with correct extensions."""
        from agent_core.audio.subtitles.generator import generate_subtitle_files

        output_stem = str(tmp_path / "scene_01_subtitles")
        result = generate_subtitle_files(sample_word_timestamps, output_stem)

        assert "srt" in result
        assert "vtt" in result

        srt_path = Path(result["srt"])
        vtt_path = Path(result["vtt"])

        assert srt_path.exists()
        assert srt_path.suffix == ".srt"
        assert vtt_path.exists()
        assert vtt_path.suffix == ".vtt"

    def test_generate_subtitle_files_creates_parent_dir(self, tmp_path, sample_word_timestamps):
        """Auto-creates subdirectories."""
        from agent_core.audio.subtitles.generator import generate_subtitle_files

        nested = tmp_path / "subdir" / "nested" / "scene_01_subtitles"
        result = generate_subtitle_files(sample_word_timestamps, str(nested))

        assert Path(result["srt"]).exists()
        assert Path(result["vtt"]).exists()

    def test_generate_subtitle_files_empty_words(self, tmp_path):
        """Empty words list: SRT is empty string, VTT is WEBVTT header."""
        from agent_core.audio.subtitles.generator import generate_subtitle_files

        result = generate_subtitle_files([], str(tmp_path / "empty"))

        assert Path(result["srt"]).exists()
        assert Path(result["vtt"]).exists()

        srt_content = Path(result["srt"]).read_text()
        vtt_content = Path(result["vtt"]).read_text()
        assert srt_content == ""
        assert vtt_content.startswith("WEBVTT")
