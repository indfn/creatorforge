"""
Tests for force alignment module.

Uses mocked faster-whisper to avoid model downloads during unit tests.
Covers word timestamp parsing, model caching, schema validation, inline
annotation, and alignment file persistence.
"""

from pathlib import Path

import pytest


class TestStripTimestamps:
    """Tests for strip_timestamps."""

    def test_strips_inline_timestamps(self):
        from agent_core.audio.alignment.aligner import strip_timestamps
        text = "Hello[0.000-0.300] world[0.350-0.500]"
        assert strip_timestamps(text) == "Hello world"

    def test_plain_text_unchanged(self):
        from agent_core.audio.alignment.aligner import strip_timestamps
        assert strip_timestamps("Hello world") == "Hello world"

    def test_empty_text(self):
        from agent_core.audio.alignment.aligner import strip_timestamps
        assert strip_timestamps("") == ""


class TestAnnotateText:
    """Tests for _annotate_text."""

    def test_basic_annotation(self):
        from agent_core.audio.alignment.aligner import _annotate_text
        words = [
            {"word": "Hello", "start": 0.0, "end": 0.3, "probability": 0.95},
            {"word": "world", "start": 0.35, "end": 0.6, "probability": 0.97},
        ]
        result = _annotate_text("Hello world", words)
        assert "Hello[0.000-0.300]" in result
        assert "world[0.350-0.600]" in result

    def test_preserves_punctuation_and_whitespace(self):
        from agent_core.audio.alignment.aligner import _annotate_text
        words = [
            {"word": "Hello", "start": 0.0, "end": 0.3, "probability": 0.95},
            {"word": "world", "start": 0.35, "end": 0.6, "probability": 0.97},
        ]
        result = _annotate_text("  Hello   world! ", words)
        assert result.startswith("  ")
        assert "world![0.350-0.600]" in result

    def test_case_insensitive_matching(self):
        from agent_core.audio.alignment.aligner import _annotate_text
        words = [{"word": "hello", "start": 0.0, "end": 0.3, "probability": 0.95}]
        result = _annotate_text("HELLO", words)
        assert "HELLO[0.000-0.300]" in result

    def test_unmatched_words_untouched(self):
        from agent_core.audio.alignment.aligner import _annotate_text
        words = [{"word": "hello", "start": 0.0, "end": 0.3, "probability": 0.95}]
        # "there" has no match — left as-is
        result = _annotate_text("hello there", words)
        assert "hello[0.000-0.300]" in result
        assert " there" in result

    def test_empty_words_list(self):
        from agent_core.audio.alignment.aligner import _annotate_text
        result = _annotate_text("hello world", [])
        assert "hello" in result
        assert "world" in result

    def test_non_word_tokens_untouched(self):
        from agent_core.audio.alignment.aligner import _annotate_text
        words = [{"word": "hello", "start": 0.0, "end": 0.3, "probability": 0.95}]
        result = _annotate_text("hello 123", words)
        assert "hello[0.000-0.300]" in result
        assert "123" in result


class TestAnnotateScriptWithTimestamps:
    """Tests for annotate_script_with_timestamps."""

    def test_rewrites_file(self, tmp_path):
        from agent_core.audio.alignment.aligner import annotate_script_with_timestamps
        script = tmp_path / "scene_01_script.txt"
        script.write_text("Hello world", encoding="utf-8")
        words = [
            {"word": "Hello", "start": 0.0, "end": 0.3, "probability": 0.95},
            {"word": "world", "start": 0.35, "end": 0.6, "probability": 0.97},
        ]
        result = annotate_script_with_timestamps(script, words)
        assert result == script
        content = script.read_text(encoding="utf-8")
        assert "Hello[0.000-0.300]" in content
        assert "world[0.350-0.600]" in content


class TestForceAlign:
    """Tests for force_align with mocked WhisperModel."""

    def _reset_whisper_cache(self):
        """Reset the module-level whisper model cache for test isolation."""
        import agent_core.audio.alignment.aligner as aligner
        aligner._whisper_model = None

    def test_force_align_empty_audio_returns_empty_list(self, mocker):
        """Mock transcribe returning no segments → expect [].

        This tests the path where the audio contains no detectable speech.
        """
        import agent_core.audio.alignment.aligner as aligner
        self._reset_whisper_cache()

        # Set up a mock that returns empty segments
        mock_instance = mocker.MagicMock()
        mock_instance.transcribe.return_value = (iter([]), None)
        aligner._whisper_model = mock_instance

        from agent_core.audio.alignment.aligner import force_align

        result = force_align(Path("/fake/empty.wav"), "hello")
        assert result is not None
        assert result == []

    def test_force_align_word_timestamps_parsed_correctly(self, mock_whisper_model):
        """Mock a segment with words, verify output format matches schema."""
        import agent_core.audio.alignment.aligner as aligner
        self._reset_whisper_cache()

        from agent_core.audio.alignment.aligner import force_align

        # Use the pre-built mock from conftest
        aligner._whisper_model = mock_whisper_model

        result = force_align(Path("/fake.wav"), "Hello world this is test")

        assert result is not None
        assert len(result) > 0

        # Verify structure matches alignment.schema.json
        for word_entry in result:
            assert "word" in word_entry
            assert "start" in word_entry
            assert "end" in word_entry
            assert "probability" in word_entry
            assert isinstance(word_entry["word"], str)
            assert isinstance(word_entry["start"], (int, float))
            assert isinstance(word_entry["end"], (int, float))
            assert isinstance(word_entry["probability"], (int, float))
            assert word_entry["start"] >= 0
            assert word_entry["probability"] <= 1.0

    def test_force_align_model_cached(self, mocker):
        """Verify the module-level cache prevents re-initialisation."""
        import agent_core.audio.alignment.aligner as aligner
        self._reset_whisper_cache()

        from agent_core.audio.alignment.aligner import force_align

        # Create a mock and set it as the cached model
        mock_instance = mocker.MagicMock()
        mock_instance.transcribe.return_value = (iter([]), None)
        aligner._whisper_model = mock_instance

        # First call — uses cached model, no import attempted
        result1 = force_align(Path("/fake1.wav"), "test")
        assert result1 is not None

        # The mock should have been reused (no new import)
        assert aligner._whisper_model is mock_instance

        # Second call — same instance
        result2 = force_align(Path("/fake2.wav"), "test")
        assert result2 is not None

    def test_alignment_output_matches_schema(self, mocker):
        """Validate alignment output against alignment.schema.json."""
        import agent_core.audio.alignment.aligner as aligner
        self._reset_whisper_cache()

        class MockWord:
            def __init__(self, word, start, end, probability):
                self.word = word
                self.start = start
                self.end = end
                self.probability = probability

        class MockSegment:
            def __init__(self, words):
                self.words = words

        words = [
            MockWord("Hello", 0.0, 0.3, 0.95),
            MockWord("world", 0.35, 0.6, 0.97),
        ]

        mock_instance = mocker.MagicMock()
        mock_instance.transcribe.return_value = (iter([MockSegment(words)]), None)
        aligner._whisper_model = mock_instance

        from agent_core.audio.alignment.aligner import force_align
        from agent_core.core.validation import validate_or_raise

        result = force_align(Path("/fake.wav"), "Hello world")

        # Schema-validate the output — should not raise
        validate_or_raise(result, "alignment.schema.json")

    def test_save_alignment_writes_json(self, tmp_path, mocker):
        """Save alignment to JSON file, verify content is correct."""
        words = [
            {"word": "Hello", "start": 0.0, "end": 0.3, "probability": 0.95},
            {"word": "world", "start": 0.35, "end": 0.6, "probability": 0.97},
        ]

        from agent_core.audio.alignment.aligner import save_alignment

        output_path = tmp_path / "alignment.json"
        result = save_alignment(words, output_path)

        assert result == output_path
        assert output_path.exists()

        import json
        loaded = json.loads(output_path.read_text(encoding="utf-8"))
        assert len(loaded) == 2
        assert loaded[0]["word"] == "Hello"
        assert loaded[1]["word"] == "world"


class TestForceAlignScenes:
    """Tests for force_align_scene convenience wrapper."""

    def test_force_align_scene_empty_script(self, tmp_path, mocker):
        """Empty transcript file should return None."""
        import agent_core.audio.alignment.aligner as aligner
        aligner._whisper_model = mocker.MagicMock()

        from agent_core.audio.alignment.aligner import force_align_scene

        empty_script = tmp_path / "empty_script.txt"
        empty_script.write_text("", encoding="utf-8")

        result = force_align_scene(Path("/fake.wav"), empty_script, annotate=False)
        assert result is None

    def test_force_align_scene_strips_existing_timestamps(self, tmp_path, mocker):
        """Script with existing timestamps should be stripped before alignment."""
        import agent_core.audio.alignment.aligner as aligner
        aligner._whisper_model = None

        # Mock with known alignment output
        class MockWord:
            def __init__(self, word, start, end, probability):
                self.word = word
                self.start = start
                self.end = end
                self.probability = probability

        class MockSegment:
            def __init__(self, words):
                self.words = words

        mock_instance = mocker.MagicMock()
        mock_instance.transcribe.return_value = (
            iter([MockSegment([
                MockWord("Hello", 0.0, 0.3, 0.95),
                MockWord("world", 0.35, 0.6, 0.97),
            ])]),
            None,
        )
        aligner._whisper_model = mock_instance

        from agent_core.audio.alignment.aligner import force_align_scene

        script = tmp_path / "scene_01_script.txt"
        script.write_text("Hello[0.1-0.2] world[0.3-0.4]", encoding="utf-8")

        result = force_align_scene(Path("/fake.wav"), script, annotate=True)
        assert result is not None
        assert len(result) == 2

        # Script should be rewritten with new timestamps
        content = script.read_text(encoding="utf-8")
        assert "Hello[0.000-0.300]" in content
        assert "world[0.350-0.600]" in content
        # Old timestamps should be gone
        assert "[0.1-0.2]" not in content

    def test_force_align_scene_annotate_false_does_not_rewrite(self, tmp_path, mocker):
        """With annotate=False, the file should not be rewritten."""
        import agent_core.audio.alignment.aligner as aligner
        aligner._whisper_model = None

        mock_instance = mocker.MagicMock()
        mock_instance.transcribe.return_value = (iter([]), None)
        aligner._whisper_model = mock_instance

        from agent_core.audio.alignment.aligner import force_align_scene

        script = tmp_path / "scene_01_script.txt"
        script.write_text("Hello world", encoding="utf-8")

        force_align_scene(Path("/fake.wav"), script, annotate=False)
        # File should still be original text (no timestamps)
        content = script.read_text(encoding="utf-8")
        assert "[0." not in content
