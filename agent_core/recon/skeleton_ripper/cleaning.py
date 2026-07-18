"""
Transcript cleaning utilities for Content Skeleton Ripper.

Provides source-specific cleaning for YouTube captions, Whisper transcripts,
and Instagram captions, plus an enhanced is_valid_transcript() validator.
"""

import re
from typing import Optional

from agent_core.recon.utils.logger import get_logger
from agent_core.recon.skeleton_ripper.cache import (
    is_valid_transcript as _cache_is_valid,
    MIN_TRANSCRIPT_WORDS,
)

logger = get_logger()

# ── Zero-width characters to strip ────────────────────────────────────────
ZERO_WIDTH_CHARS = re.compile(r"[\u200b\u200c\u200d\ufeff]")

# ── YouTube caption / VTT artifacts ────────────────────────────────────────
VTT_BRACKET_ARTIFACTS = re.compile(
    r"\[[^\]]*\]",
    re.IGNORECASE,
)
VTT_HEADER_LINES = re.compile(r"^(WEBVTT|Kind:|Language:)", re.MULTILINE)
VTT_TIMING_LINE = re.compile(r"^\d{2}:|-->")
VTT_HTML_ENTITIES = re.compile(r"&(?:amp|lt|gt|quot|apos|nbsp);")
VTT_CUE_NUMBER = re.compile(r"^\d+$")

# ── Repeated consecutive words (youtube_caption) ──────────────────────────
REPEATED_WORD = re.compile(r"\b(\w+)\s+\1\b", re.IGNORECASE)

# ── Multi-space normalization ─────────────────────────────────────────────
MULTI_SPACE = re.compile(r"[ \t]+")

# ── Unicode smart quotes → ASCII ──────────────────────────────────────────
UNICODE_QUOTES = {
    "\u201c": '"',
    "\u201d": '"',
    "\u2018": "'",
    "\u2019": "'",
    "\u201e": '"',
    "\u201f": '"',
}


def _replace_unicode_quotes(text: str) -> str:
    """Replace Unicode smart quotes with ASCII equivalents."""
    for u_char, ascii_char in UNICODE_QUOTES.items():
        text = text.replace(u_char, ascii_char)
    return text


def _strip_zero_width(text: str) -> str:
    """Remove zero-width and invisible Unicode characters."""
    return ZERO_WIDTH_CHARS.sub("", text)


def _normalize_whitespace(text: str) -> str:
    """Collapse multiple spaces/tabs into single space, strip edges."""
    text = MULTI_SPACE.sub(" ", text)
    return text.strip()


def _strip_incomplete_sentence(text: str) -> str:
    """
    Strip trailing words that don't end in sentence-ending punctuation.

    Walks backward through sentences to find the last complete one.
    If no sentence-ending punctuation is found at all, returns the original text
    rather than stripping everything.
    """
    text = text.strip()
    if not text:
        return ""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    # If there's only one "sentence" and it doesn't end with punctuation,
    # it means there's no sentence boundary at all — return original text.
    if len(sentences) <= 1:
        return text
    last = sentences[-1].strip()
    if last and not re.search(r"[.!?]$", last):
        sentences = sentences[:-1]
    result = " ".join(sentences).strip()
    return result if result else text


def _clean_youtube_caption(raw: str) -> str:
    """Clean YouTube VTT caption text."""
    text = raw

    # Strip VTT bracket artifacts: [Music], [Applause], etc.
    text = VTT_BRACKET_ARTIFACTS.sub("", text)

    # Strip WEBVTT header lines
    text = VTT_HEADER_LINES.sub("", text)

    # Strip cue timing lines and cue numbering
    lines = text.splitlines()
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped and (VTT_TIMING_LINE.match(stripped) or VTT_CUE_NUMBER.match(stripped)):
            continue
        cleaned_lines.append(stripped)

    text = "\n".join(cleaned_lines)

    # Strip HTML entities
    text = VTT_HTML_ENTITIES.sub("", text)

    # Collapse repeated consecutive words (the the → the)
    prev = ""
    while prev != text:
        prev = text
        text = REPEATED_WORD.sub(r"\1", text)

    return text


def _clean_whisper(raw: str) -> str:
    """Clean Whisper API transcript text."""
    text = raw

    # Strip incomplete trailing sentence
    text = _strip_incomplete_sentence(text)

    return text


def _clean_instagram_caption(raw: str) -> str:
    """Clean Instagram caption text."""
    text = raw

    # Normalize Unicode quotes to ASCII
    text = _replace_unicode_quotes(text)

    # Strip leading/trailing whitespace
    text = text.strip()

    # Normalize multi-space to single (but keep intentional newlines)
    lines = text.splitlines()
    normalized_lines = [MULTI_SPACE.sub(" ", line).strip() for line in lines]
    # Collapse >2 consecutive blank lines to exactly 1 blank line
    result_lines = []
    blank_count = 0
    for line in normalized_lines:
        if not line:
            blank_count += 1
            if blank_count == 1:
                result_lines.append("")
        else:
            blank_count = 0
            result_lines.append(line)
    # Strip trailing blank lines
    while result_lines and not result_lines[-1]:
        result_lines.pop()
    text = "\n".join(result_lines)

    return text


def clean_transcript(raw: str, source: str = "whisper") -> str:
    """
    Clean a raw transcript string based on its source.

    Args:
        raw: Raw transcript text.
        source: One of "youtube_caption", "whisper", "instagram_caption".
                Defaults to "whisper".

    Returns:
        Cleaned transcript string, or empty string on failure.
    """
    if not raw or not isinstance(raw, str):
        return ""

    try:
        text = raw

        # Apply source-specific cleaning
        if source == "youtube_caption":
            text = _clean_youtube_caption(text)
        elif source == "whisper":
            text = _clean_whisper(text)
        elif source == "instagram_caption":
            text = _clean_instagram_caption(text)

        # Always: strip zero-width characters
        text = _strip_zero_width(text)

        # Always: normalize whitespace (re-run for any touch-ups)
        text = _normalize_whitespace(text)

        # Return empty string if nothing left
        return text if text else ""

    except Exception as e:
        logger.warning("CLEANING", f"Error cleaning transcript: {e}")
        return ""


def is_valid_transcript(
    transcript: str,
    min_words: int = MIN_TRANSCRIPT_WORDS,
    min_word_length: int = 1,
) -> bool:
    """
    Check whether a transcript is long enough and has meaningful words.

    Args:
        transcript: The transcript text to validate.
        min_words: Minimum number of words required (default: MIN_TRANSCRIPT_WORDS).
        min_word_length: Minimum length for each word. If any word has fewer
                         characters than this, the transcript is invalid.
                         Defaults to 1 (no filtering).

    Returns:
        True if the transcript is valid, False otherwise.
    """
    return _cache_is_valid(transcript, min_words=min_words, min_word_length=min_word_length)
