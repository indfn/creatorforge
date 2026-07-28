"""
Force alignment — word-level timestamp extraction.

Primary method: Groq Whisper API (``GROQ_API_KEY`` env var) for cloud-based
transcription with word-level timestamps. Falls back to local faster-whisper
(``tiny`` model, ``vad_filter=True``) if no Groq key is available or the API
call fails.

Per-scene ``_script.txt`` files are rewritten with inline timestamps after
alignment — the file becomes the single canonical timestamp artifact, so
separate ``_alignment.json`` files are unnecessary.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Optional

from agent_core.core.validation import validate_or_raise

logger = logging.getLogger(__name__)

# Pattern for inline timestamps: ``word[START-END]``
_TIMESTAMP_RE = re.compile(r"\[(\d+\.\d+)-(\d+\.\d+)\]")

# ---------------------------------------------------------------------------
# Module-level model cache — WhisperModel is ~150 MB to load, so we load it
# once and reuse across scenes. The first load triggers a Hugging Face Hub
# download (logged at INFO).
# ---------------------------------------------------------------------------

_whisper_model = None


def _get_model(model_size: str = "tiny", device: str = "cpu", compute_type: str = "int8"):
    """Return the cached faster-whisper model, loading on first call."""
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel

        logger.info(
            "Loading faster-whisper %s model on %s (compute_type=%s) — "
            "first load may download from Hugging Face Hub",
            model_size,
            device,
            compute_type,
        )
        _whisper_model = WhisperModel(model_size, device=device, compute_type=compute_type)
    return _whisper_model


# ---------------------------------------------------------------------------
# Groq Whisper API
# ---------------------------------------------------------------------------


def _align_via_groq(
    audio_path: Path,
    transcript: str,
    language: str = "en",
) -> Optional[list[dict]]:
    """Align via Groq Whisper API (``GROQ_API_KEY`` env var).

    Uses Groq's ``whisper-large-v3-turbo`` model with ``timestamp_granularities=["word"]``
    for word-level timestamps. Returns parsed alignment or ``None`` on failure.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        logger.debug("Groq alignment: GROQ_API_KEY not set — skipping")
        return None

    try:
        from groq import Groq

        client = Groq(api_key=api_key)

        with open(audio_path, "rb") as f:
            translation = client.audio.transcriptions.create(
                file=(audio_path.name, f.read()),
                model="whisper-large-v3-turbo",
                response_format="verbose_json",
                timestamp_granularities=["word"],
                language=language,
                prompt=transcript,
            )

        words = []
        if hasattr(translation, "words") and translation.words:
            for w in translation.words:
                words.append({
                    "word": w.word.strip(),
                    "start": round(w.start, 3),
                    "end": round(w.end, 3),
                    "probability": 1.0,
                })

        if not words:
            logger.info("Groq alignment: no words returned")
            return []

        validate_or_raise(words, "alignment.schema.json")
        logger.debug("Groq aligned %d words from %s", len(words), audio_path)
        return words

    except Exception:
        logger.warning("Groq alignment failed for %s", audio_path, exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Local faster-whisper fallback
# ---------------------------------------------------------------------------


def _align_via_local(
    audio_path: Path,
    transcript: str,
    language: str = "en",
) -> Optional[list[dict]]:
    """Align via local faster-whisper model (fallback)."""
    model = _get_model()

    try:
        segments, _info = model.transcribe(
            str(audio_path),
            word_timestamps=True,
            vad_filter=True,
            vad_parameters=dict(
                threshold=0.5,
                min_silence_duration_ms=500,
                speech_pad_ms=400,
            ),
            language=language,
            initial_prompt=transcript,
            beam_size=3,
        )

        segments_list = list(segments)
        words = []
        for segment in segments_list:
            if not segment.words:
                continue
            for word in segment.words:
                words.append({
                    "word": word.word.strip(),
                    "start": round(word.start, 3),
                    "end": round(word.end, 3),
                    "probability": round(word.probability, 3),
                })

        if not words:
            logger.info("Local alignment: no words detected (silence or empty file)")
            return []

        validate_or_raise(words, "alignment.schema.json")
        logger.debug("Local aligned %d words from %s", len(words), audio_path)
        return words

    except Exception:
        logger.warning("Local alignment failed for %s", audio_path, exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Timestamp annotation helpers
# ---------------------------------------------------------------------------


def strip_timestamps(text: str) -> str:
    """Remove inline timestamps (``word[START-END]``) from text.

    Args:
        text: Text possibly containing ``word[0.000-0.300]`` annotations.

    Returns:
        Clean text with all ``[START-END]`` markers removed.
    """
    return _TIMESTAMP_RE.sub("", text).strip()


def _normalize_word(word: str) -> str:
    """Strip punctuation and lowercase for fuzzy word matching."""
    return word.lower().strip(".,!?;:'\"()[]{}·•")


def annotate_script_with_timestamps(script_path: Path, words: list[dict]) -> Optional[Path]:
    """Rewrite a scene script file with inline word timestamps.

    The original text structure (whitespace, punctuation) is preserved.
    Each word that has a matching alignment entry gets ``word[START-END]``
    appended. Words with no matching alignment entry are left as-is.

    Args:
        script_path: Path to the ``_script.txt`` file to annotate.
        words: List of ``{"word", "start", "end", "probability"}`` dicts.

    Returns:
        ``script_path`` on success, ``None`` on failure.
    """
    try:
        raw = script_path.read_text(encoding="utf-8")
        clean = strip_timestamps(raw)  # strip any old timestamps first
        annotated = _annotate_text(clean, words)
        script_path.write_text(annotated, encoding="utf-8")
        logger.info("Annotated %s with %d word timestamps", script_path, len(words))
        return script_path
    except Exception:
        logger.warning("Failed to annotate %s", script_path, exc_info=True)
        return None


def _annotate_text(text: str, words: list[dict]) -> str:
    """Annotate each word in *text* with ``[START-END]`` from alignment data.

    Splits on ``\\s+`` to preserve original whitespace.  Matches each
    whitespace-delimited token against the next alignment word (case-
    and punctuation-insensitive).  Non-word tokens (numbers, symbols)
    are left unchanged.
    """
    word_idx = 0
    parts: list[str] = []

    for part in re.split(r"(\s+)", text):
        if not part or part.isspace():
            parts.append(part)
            continue

        # Check if this token looks like a word (has at least one letter)
        stripped = part.strip(".,!?;:'\"()[]{}·•")
        if not stripped or not any(c.isalpha() for c in stripped):
            parts.append(part)
            continue

        # Try to match with current alignment word
        if word_idx < len(words):
            al_word = _normalize_word(words[word_idx]["word"])
            if al_word and _normalize_word(stripped) == al_word:
                ts = words[word_idx]
                parts.append(f"{part}[{ts['start']:.3f}-{ts['end']:.3f}]")
                word_idx += 1
                continue

        parts.append(part)

    return "".join(parts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def force_align(
    audio_path: Path,
    transcript: str,
    language: str = "en",
) -> Optional[list[dict]]:
    """Force-align an audio file with its known transcript.

    Primary: Groq Whisper API (``whisper-large-v3-turbo``, word-level timestamps).
    Fallback: local faster-whisper (``tiny``, ``vad_filter=True``).

    Parameters
    ----------
    audio_path:
        Path to the audio file.
    transcript:
        The known scene transcript used as prompt for decoding bias.
    language:
        ISO 639-1 language code (default ``"en"``).

    Returns
    -------
    List of ``{"word", "start", "end", "probability"}`` dicts, or ``None``.
    """
    # Try Groq API first
    words = _align_via_groq(audio_path, transcript, language=language)
    if words is not None:
        return words

    # Fallback to local faster-whisper
    logger.info("Groq unavailable, falling back to local faster-whisper alignment")
    return _align_via_local(audio_path, transcript, language=language)


def force_align_scene(
    audio_path: Path,
    scene_script_path: Path,
    language: str = "en",
    annotate: bool = True,
) -> Optional[list[dict]]:
    """
    Convenience wrapper: read a scene script from file, force-align, and
    optionally rewrite the script file with inline timestamps.

    The script file is read, any existing inline timestamps are stripped
    (so re-alignment works cleanly), and the clean transcript is used as
    the alignment prompt.  After alignment the file is rewritten with
    ``word[START-END]`` annotations if *annotate* is ``True``.

    Parameters
    ----------
    audio_path:
        Path to the scene audio file.
    scene_script_path:
        Path to a text file containing the scene transcript.
    language:
        ISO 639-1 language code (default ``"en"``).
    annotate:
        If ``True`` (default), rewrite *scene_script_path* with inline
        timestamps after successful alignment.

    Returns
    -------
    List of ``{"word", "start", "end", "probability"}`` dicts, or ``None``.
    """
    raw = scene_script_path.read_text(encoding="utf-8")
    transcript = strip_timestamps(raw)
    if not transcript:
        logger.warning("Empty transcript in %s — skipping alignment", scene_script_path)
        return None

    words = force_align(audio_path, transcript, language=language)
    if words is not None and annotate:
        annotate_script_with_timestamps(scene_script_path, words)
    return words


def save_alignment(words: list[dict], output_path: Path) -> Optional[Path]:
    """
    Validate word-level alignment data and write to JSON.

    Parameters
    ----------
    words:
        List of ``{"word", "start", "end", "probability"}`` dicts.
    output_path:
        Destination path for the JSON file.

    Returns
    -------
    ``output_path`` on success, ``None`` on failure.
    """
    try:
        validate_or_raise(words, "alignment.schema.json")
        output_path.write_text(
            json.dumps(words, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info("Saved alignment (%d words) to %s", len(words), output_path)
        return output_path
    except Exception:
        logger.warning("Failed to save alignment to %s", output_path, exc_info=True)
        return None


# ---------------------------------------------------------------------------
# CLI entry point — standalone testing
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Force-align audio with transcript")
    parser.add_argument("--audio", required=True, help="Path to audio file")
    parser.add_argument("--transcript", required=True, help="Path to transcript text file")
    parser.add_argument("--output", required=True, help="Output JSON path")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    words = force_align_scene(Path(args.audio), Path(args.transcript))
    if words is not None:
        save_alignment(words, Path(args.output))
        print(f"Aligned {len(words)} words, saved to {args.output}")
    else:
        print("Alignment failed", file=sys.stderr)
        sys.exit(1)
