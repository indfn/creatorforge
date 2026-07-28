"""
SRT/VTT subtitle generation from word-level force alignment data.

Converts a list of ``{"word", "start", "end", "probability"}`` dicts into
standard SRT and WebVTT subtitle formats.  Groups words into subtitle cues
by natural pauses (>500 ms gap) and character limits (default 42 per line).

No embedded styling per D-08.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _format_timestamp(seconds: float, srt_format: bool = True) -> str:
    """
    Convert a float *seconds* value to a timestamp string.

    Parameters
    ----------
    seconds:
        Time in seconds.
    srt_format:
        If ``True`` use SRT-style comma decimal separator (``HH:MM:SS,mmm``),
        otherwise use VTT-style dot (``HH:MM:SS.mmm``).

    Returns
    -------
    Formatted timestamp string.
    """
    # Clamp edge cases.
    if seconds < 0:
        seconds = 0.0
    if seconds > 359999:  # 99:59:59
        seconds = 359999.0

    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60

    formatted = f"{h:02d}:{m:02d}:{s:06.3f}"
    if srt_format:
        formatted = formatted.replace(".", ",")
    return formatted


def _group_words(words: list[dict], max_chars: int = 42) -> list[list[dict]]:
    """
    Group consecutive words into subtitle cue chunks.

    A new group is started when:
    1. Adding the next word would exceed *max_chars* characters, OR
    2. The gap between the current word's end and the next word's start
       exceeds 0.5 seconds (natural pause).

    Parameters
    ----------
    words:
        List of word dicts (must have ``"word"``, ``"start"``, ``"end"`` keys).
    max_chars:
        Maximum characters per subtitle cue (default 42).

    Returns
    -------
    List of word groups, where each group is a list of word dicts.
    """
    if not words:
        return []
    if len(words) == 1:
        return [words]

    groups: list[list[dict]] = []
    current_group = [words[0]]
    current_text = words[0]["word"]

    for next_word in words[1:]:
        gap = next_word["start"] - current_group[-1]["end"]
        would_be_text = current_text + " " + next_word["word"]

        if gap > 0.5 or len(would_be_text) > max_chars:
            # Start a new group.
            groups.append(current_group)
            current_group = [next_word]
            current_text = next_word["word"]
        else:
            current_group.append(next_word)
            current_text = would_be_text

    if current_group:
        groups.append(current_group)

    return groups


# ---------------------------------------------------------------------------
# SRT generation
# ---------------------------------------------------------------------------


def generate_srt(words: list[dict], max_chars: int = 42) -> str:
    """
    Generate SRT subtitle content from word-level alignment data.

    Format per the SRT specification::

        1
        HH:MM:SS,mmm --> HH:MM:SS,mmm
        First subtitle line

        2
        HH:MM:SS,mmm --> HH:MM:SS,mmm
        Second subtitle line

    Parameters
    ----------
    words:
        List of ``{"word", "start", "end", "probability"}`` dicts.
    max_chars:
        Maximum characters per subtitle cue line (default 42).

    Returns
    -------
    SRT content as a string, or ``""`` if *words* is empty.
    """
    if not words:
        return ""

    groups = _group_words(words, max_chars=max_chars)
    lines: list[str] = []

    for idx, group in enumerate(groups, start=1):
        start_ts = _format_timestamp(group[0]["start"], srt_format=True)
        end_ts = _format_timestamp(group[-1]["end"], srt_format=True)

        # Build subtitle text — max 2 lines.
        text_parts: list[str] = []
        current_line = ""
        for w in group:
            word_text = w["word"]
            if current_line:
                candidate = current_line + " " + word_text
            else:
                candidate = word_text

            if len(candidate) > max_chars and current_line:
                text_parts.append(current_line)
                current_line = word_text
            else:
                current_line = candidate

            if len(text_parts) == 2:
                # Max 2 lines — break; remaining words join the last line.
                break

        if current_line:
            text_parts.append(current_line)

        # If we broke early, append remaining words to the last line.
        assigned_count = sum(len(p.split()) for p in text_parts)
        if assigned_count < len(group):
            extra = " ".join(w["word"] for w in group[assigned_count:])
            text_parts[-1] = text_parts[-1] + " " + extra

        subtitle_text = "\n".join(text_parts)

        lines.append(f"{idx}")
        lines.append(f"{start_ts} --> {end_ts}")
        lines.append(subtitle_text)
        lines.append("")  # empty line between cues

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# WebVTT generation
# ---------------------------------------------------------------------------


def generate_vtt(words: list[dict], max_chars: int = 42) -> str:
    """
    Generate WebVTT subtitle content from word-level alignment data.

    Format per the W3C WebVTT spec::

        WEBVTT

        HH:MM:SS.mmm --> HH:MM:SS.mmm
        First subtitle line

        HH:MM:SS.mmm --> HH:MM:SS.mmm
        Second subtitle line

    Parameters
    ----------
    words:
        List of ``{"word", "start", "end", "probability"}`` dicts.
    max_chars:
        Maximum characters per subtitle cue line (default 42).

    Returns
    -------
    WebVTT content as a string, or ``"WEBVTT\\n"`` if *words* is empty.
    """
    if not words:
        return "WEBVTT\n"

    groups = _group_words(words, max_chars=max_chars)
    lines: list[str] = ["WEBVTT", ""]  # header + blank line

    for group in groups:
        start_ts = _format_timestamp(group[0]["start"], srt_format=False)
        end_ts = _format_timestamp(group[-1]["end"], srt_format=False)

        # Build subtitle text — max 2 lines (same logic as SRT).
        text_parts: list[str] = []
        current_line = ""
        for w in group:
            word_text = w["word"]
            if current_line:
                candidate = current_line + " " + word_text
            else:
                candidate = word_text

            if len(candidate) > max_chars and current_line:
                text_parts.append(current_line)
                current_line = word_text
            else:
                current_line = candidate

            if len(text_parts) == 2:
                break

        if current_line:
            text_parts.append(current_line)

        assigned_count = sum(len(p.split()) for p in text_parts)
        if assigned_count < len(group):
            extra = " ".join(w["word"] for w in group[assigned_count:])
            text_parts[-1] = text_parts[-1] + " " + extra

        subtitle_text = "\n".join(text_parts)

        lines.append(f"{start_ts} --> {end_ts}")
        lines.append(subtitle_text)
        lines.append("")  # empty line between cues

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------


def generate_subtitle_files(
    words: list[dict],
    output_stem: str,
    max_chars: int = 42,
) -> dict[str, Path]:
    """
    Generate both SRT and VTT subtitle files from word-level alignment data.

    Parameters
    ----------
    words:
        List of ``{"word", "start", "end", "probability"}`` dicts.
    output_stem:
        File path stem (e.g. ``"/output/scene_01_subtitles"``).  The actual
        files created are ``{output_stem}.srt`` and ``{output_stem}.vtt``.
    max_chars:
        Maximum characters per subtitle cue line (default 42).

    Returns
    -------
    Dict with keys ``"srt"`` and ``"vtt"`` mapping to the written file paths.
    """
    output_path = Path(output_stem)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    srt_path = output_path.with_suffix(".srt")
    vtt_path = output_path.with_suffix(".vtt")

    try:
        srt_content = generate_srt(words, max_chars=max_chars)
        srt_path.write_text(srt_content, encoding="utf-8")
    except Exception as e:
        logger.error("Failed to write SRT file to %s: %s", srt_path, e)

    try:
        vtt_content = generate_vtt(words, max_chars=max_chars)
        vtt_path.write_text(vtt_content, encoding="utf-8")
    except Exception as e:
        logger.error("Failed to write VTT file to %s: %s", vtt_path, e)

    logger.info("Wrote subtitle files: %s, %s", srt_path, vtt_path)

    return {"srt": srt_path, "vtt": vtt_path}


# ---------------------------------------------------------------------------
# Convenience aliases — match the naming used in the project's verification
# scripts and external callers.
# ---------------------------------------------------------------------------

words_to_srt = generate_srt
"""Alias for :func:`generate_srt`."""
words_to_vtt = generate_vtt
"""Alias for :func:`generate_vtt`."""
write_subtitle_files = generate_subtitle_files
"""Alias for :func:`generate_subtitle_files`."""
