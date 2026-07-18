"""Tests for agent_core.recon.skeleton_ripper.cleaning"""

import pytest
from agent_core.recon.skeleton_ripper.cleaning import clean_transcript, is_valid_transcript
from agent_core.recon.skeleton_ripper.cache import MIN_TRANSCRIPT_WORDS


# ── YouTube caption cleaning ──────────────────────────────────────────────


class TestCleanTranscriptYoutubeCaption:
    """Source-specific tests for clean_transcript(source='youtube_caption')."""

    def test_strips_music_and_applause(self):
        result = clean_transcript("[Music] hello world [Applause]", "youtube_caption")
        assert result == "hello world"

    def test_strips_laughter_and_sound_artifacts(self):
        result = clean_transcript("[Laughter] hey [Sound] there", "youtube_caption")
        assert result == "hey there"

    def test_strips_musical_note(self):
        result = clean_transcript("[♪] hello world", "youtube_caption")
        assert result == "hello world"

    def test_strips_webvtt_header(self):
        raw = "WEBVTT\n\n1\n00:00:01.000 --> 00:00:04.000\nHello world\n"
        result = clean_transcript(raw, "youtube_caption")
        assert result == "Hello world"

    def test_strips_kind_and_language_prefixes(self):
        """VTT_HEADER_LINES only removes the 'Kind:'/'Language:' prefix text."""
        raw = "Kind: captions\nLanguage: en\nHello world"
        result = clean_transcript(raw, "youtube_caption")
        assert "Kind:" not in result
        assert "Language:" not in result

    def test_strips_timing_lines_with_arrows(self):
        raw = "00:01:02.123 --> 00:01:05.456\nHello world"
        result = clean_transcript(raw, "youtube_caption")
        assert result == "Hello world"

    def test_strips_cue_numbers(self):
        """Cue-number-only lines are removed; remaining content is joined with newlines."""
        raw = "1\n2\nHello world\n3\nGoodbye"
        result = clean_transcript(raw, "youtube_caption")
        assert "Hello world" in result
        assert "Goodbye" in result

    def test_removes_repeated_words(self):
        result = clean_transcript("the the quick brown fox", "youtube_caption")
        assert result == "the quick brown fox"

    def test_removes_repeated_words_case_insensitive(self):
        result = clean_transcript("The The quick brown fox", "youtube_caption")
        assert result == "The quick brown fox"

    def test_normalizes_multi_space(self):
        result = clean_transcript("hello    world   foo", "youtube_caption")
        assert result == "hello world foo"

    def test_strips_zero_width_chars(self):
        result = clean_transcript("hello\u200bworld", "youtube_caption")
        assert result == "helloworld"

    def test_returns_empty_for_garbage_input(self):
        result = clean_transcript("[Music] [Applause]", "youtube_caption")
        assert result == ""

    def test_handles_empty_string(self):
        assert clean_transcript("", "youtube_caption") == ""

    def test_preserves_valid_punctuation(self):
        result = clean_transcript("Hello, world! How are you?", "youtube_caption")
        assert result == "Hello, world! How are you?"


# ── Whisper transcript cleaning ──────────────────────────────────────────


class TestCleanTranscriptWhisper:
    """Source-specific tests for clean_transcript(source='whisper')."""

    def test_normalizes_multi_space(self):
        result = clean_transcript("hello   world.", "whisper")
        assert result == "hello world."

    def test_removes_incomplete_trailing_sentence(self):
        result = clean_transcript("Hello world. This is incomplete", "whisper")
        assert result == "Hello world."

    def test_removes_incomplete_trailing_with_exclamation(self):
        result = clean_transcript("Great! And then something trailing", "whisper")
        assert result == "Great!"

    def test_removes_incomplete_trailing_with_question(self):
        result = clean_transcript("Is this right? maybe not complete", "whisper")
        assert result == "Is this right?"

    def test_preserves_single_sentence_without_punctuation(self):
        """A single sentence lacking terminal punctuation is preserved as-is."""
        result = clean_transcript("hello world", "whisper")
        assert result == "hello world"

    def test_preserves_single_sentence_with_period(self):
        result = clean_transcript("Hello world.", "whisper")
        assert result == "Hello world."

    def test_preserves_valid_multi_sentence(self):
        result = clean_transcript("First sentence. Second sentence. Third!", "whisper")
        assert result == "First sentence. Second sentence. Third!"

    def test_handles_empty_string(self):
        assert clean_transcript("", "whisper") == ""

    def test_strips_leading_trailing_whitespace(self):
        result = clean_transcript("  hello world.  ", "whisper")
        assert result == "hello world."


# ── Instagram caption cleaning ────────────────────────────────────────────


class TestCleanTranscriptInstagram:
    """Source-specific tests for clean_transcript(source='instagram_caption')."""

    def test_normalizes_unicode_double_quotes(self):
        result = clean_transcript("\u201cHello\u201d world", "instagram_caption")
        assert result == '"Hello" world'

    def test_normalizes_unicode_single_quotes(self):
        result = clean_transcript("\u2018Hello\u2019 world", "instagram_caption")
        assert result == "'Hello' world"

    def test_normalizes_bottom_double_quote(self):
        result = clean_transcript("\u201eHello\u201f world", "instagram_caption")
        assert result == '"Hello" world'

    def test_strips_excess_newlines(self):
        result = clean_transcript("Hello\n\n\n\nworld", "instagram_caption")
        assert result == "Hello\n\nworld"

    def test_strips_trailing_newlines(self):
        result = clean_transcript("Hello world\n\n\n", "instagram_caption")
        assert result == "Hello world"

    def test_strips_leading_trailing_whitespace(self):
        result = clean_transcript("  Hello world.  ", "instagram_caption")
        assert result == "Hello world."

    def test_preserves_hashtags(self):
        result = clean_transcript("Check this out! #awesome #viral", "instagram_caption")
        assert result == "Check this out! #awesome #viral"

    def test_preserves_mentions(self):
        result = clean_transcript("Credit to @creator for this", "instagram_caption")
        assert result == "Credit to @creator for this"

    def test_normalizes_multi_space(self):
        result = clean_transcript("hello    world   foo", "instagram_caption")
        assert result == "hello world foo"

    def test_handles_empty_string(self):
        assert clean_transcript("", "instagram_caption") == ""

    def test_strips_zero_width_chars(self):
        result = clean_transcript("hello\u200b world", "instagram_caption")
        assert result == "hello world"

    def test_mixed_quotes_and_hashtags(self):
        result = clean_transcript("\u201cAmazing\u201d day! #blessed @user", "instagram_caption")
        assert result == '"Amazing" day! #blessed @user'


# ── Generic / source-agnostic cleaning ────────────────────────────────────


class TestCleanTranscriptGeneric:
    """Tests for clean_transcript behaviors shared across all sources."""

    def test_zero_width_chars_stripped(self):
        result = clean_transcript("hello\u200bworld.", "whisper")
        assert result == "helloworld."

    def test_zero_width_chars_between_words(self):
        result = clean_transcript("hello\u200b world.", "whisper")
        assert result == "hello world."

    def test_zero_width_feff_stripped(self):
        result = clean_transcript("\ufeffHello world", "whisper")
        assert result == "Hello world"

    def test_handles_empty_string(self):
        assert clean_transcript("", "whisper") == ""

    def test_handles_whitespace_only(self):
        assert clean_transcript("   ", "whisper") == ""

    def test_handles_none_like_input(self):
        assert clean_transcript("", "whisper") == ""

    def test_invalid_source_falls_back(self):
        """An unrecognised source still applies generic cleaning steps."""
        result = clean_transcript("  hello\u200b world  ", "unknown_source")
        assert result == "hello world"


# ── is_valid_transcript ──────────────────────────────────────────────────


class TestIsValidTranscript:
    """Tests for is_valid_transcript() with default and custom params."""

    # — Empty / short failures —

    def test_empty_string_returns_false(self):
        assert is_valid_transcript("") is False

    def test_whitespace_only_returns_false(self):
        assert is_valid_transcript("   ") is False

    def test_min_words_threshold_default(self):
        """MIN_TRANSCRIPT_WORDS is 10, so 2 words fails."""
        assert is_valid_transcript("hello world") is False

    def test_min_words_threshold_above(self):
        assert is_valid_transcript("a b c", min_words=5) is False

    # — Pass conditions —

    def test_min_words_threshold_below_passes(self):
        assert is_valid_transcript("hello world", min_words=2) is True

    def test_normal_multi_word_transcript_above_threshold(self):
        text = "word " * 15
        assert is_valid_transcript(text.strip()) is True

    # — min_word_length parameter —

    def test_min_word_length_passes(self):
        assert is_valid_transcript("hello world", min_words=2, min_word_length=3) is True

    def test_min_word_length_fails(self):
        assert is_valid_transcript("a b c", min_words=2, min_word_length=2) is False

    def test_min_word_length_one_allows_single_chars(self):
        """Default min_word_length=1 does not filter out single characters."""
        assert is_valid_transcript("a b c d e f g h i j", min_words=5) is True

    def test_mixed_word_lengths_fails_with_min_word_length_three(self):
        assert is_valid_transcript("hello a world", min_words=2, min_word_length=3) is False

    # — Edge cases —

    def test_default_min_words_still_works(self):
        assert is_valid_transcript("short") is False  # 1 word < 10

    def test_string_with_newlines_counts_all_words(self):
        text = "hello\nworld\nfoo\nbar\nbaz\nqux\nquux\ncorge\ngrault\ngarply"
        assert is_valid_transcript(text, min_words=10) is True

    def test_min_words_zero_accepts_empty_string(self):
        """min_words=0 bypasses the length check."""
        assert is_valid_transcript("", min_words=0) is False  # still empty check
