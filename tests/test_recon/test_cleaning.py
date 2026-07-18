"""Tests for agent_core.recon.skeleton_ripper.cleaning"""

import pytest
from agent_core.recon.skeleton_ripper.cleaning import clean_transcript, is_valid_transcript


class TestCleanTranscript:
    def test_youtube_caption_strips_music_and_applause(self):
        result = clean_transcript("[Music] hello world [Applause]", "youtube_caption")
        assert result == "hello world"

    def test_youtube_caption_strips_webvtt_header(self):
        raw = "WEBVTT\n\n1\n00:00:01.000 --> 00:00:04.000\nHello world\n"
        result = clean_transcript(raw, "youtube_caption")
        assert result == "Hello world"

    def test_youtube_caption_removes_repeated_words(self):
        result = clean_transcript("the the quick brown fox", "youtube_caption")
        assert result == "the quick brown fox"

    def test_whisper_normalizes_multi_space(self):
        result = clean_transcript("hello   world", "whisper")
        assert result == "hello world"

    def test_whisper_removes_incomplete_trailing_sentence(self):
        result = clean_transcript("Hello world. This is incomplete", "whisper")
        assert result == "Hello world."

    def test_instagram_normalizes_unicode_quotes(self):
        result = clean_transcript("\u201cHello\u201d world", "instagram_caption")
        assert result == '"Hello" world'

    def test_instagram_strips_excess_newlines(self):
        result = clean_transcript("Hello\n\n\n\nworld", "instagram_caption")
        assert result == "Hello\n\nworld"

    def test_empty_result_returns_empty_string(self):
        result = clean_transcript("[Music] [Applause]", "youtube_caption")
        assert result == ""

    def test_zero_width_chars_stripped(self):
        result = clean_transcript("hello\u200bworld", "whisper")
        assert result == "hello world"


class TestIsValidTranscript:
    def test_empty_string_returns_false(self):
        assert is_valid_transcript("") is False

    def test_valid_short_string_returns_true(self):
        assert is_valid_transcript("hello world") is True

    def test_min_words_threshold(self):
        assert is_valid_transcript("a b c", min_words=5) is False

    def test_min_word_length_passes(self):
        assert is_valid_transcript("hello world", min_word_length=3) is True

    def test_min_word_length_fails(self):
        assert is_valid_transcript("a b c", min_word_length=2) is False

    def test_default_min_words_still_works(self):
        assert is_valid_transcript("short") is False  # 1 word < 10
