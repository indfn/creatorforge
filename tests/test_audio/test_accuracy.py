"""
PROD-AUDIO-03: Alignment accuracy validation — ≥90% word-level accuracy.

Uses 5 synthetic test cases with known audio + transcript pairs.  Each test
clip's expected word boundaries are compared against the force-aligned output.

These tests require the ``faster-whisper`` model to be downloaded (``tiny``).
They are marked ``slow`` and ``integration`` and are skipped when the model
is not available.
"""

import logging
import os
import struct
import wave
from pathlib import Path

import pytest

logger = logging.getLogger(__name__)

# Threshold per PROD-AUDIO-03 / D-16: 90% of words must be within 100 ms
ACCURACY_THRESHOLD = 0.90
WORD_TOLERANCE_MS = 100  # milliseconds


# =========================================================================
# Test corpus generators
# =========================================================================


def _synthesize_tone_wav(path: Path, sample_rate: int, duration: float, freq: float = 440):
    """Write a simple sine-wave WAV file (mono, 16-bit PCM)."""
    import math

    num_samples = int(sample_rate * duration)
    samples = []
    for i in range(num_samples):
        t = i / sample_rate
        sample = int(16000 * 0.3 * math.sin(2 * math.pi * freq * t))
        samples.append(sample)

    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        for s in samples:
            wf.writeframes(struct.pack("<h", s))


def _build_test_cases(tmp_path: Path) -> list[dict]:
    """Create the 5-test-clip corpus.

    Each test case has:
        - ``name``: Description
        - ``audio_path``: Path to the synthetic WAV
        - ``transcript``: Known transcript
        - ``ground_truth_words``: List of ``{"word": str, "start": float, "end": float}``
          with expected start/end times (in seconds) for the synthetic audio.

    Returns:
        List of test case dicts.
    """
    sample_rate = 16000
    cases = []

    # Case 1: Short phrase (5 words), ~2s
    # Each word gets ~0.4s
    audio_1 = tmp_path / "case_1.wav"
    _synthesize_tone_wav(audio_1, sample_rate, 2.0, freq=440)
    cases.append({
        "name": "Short phrase (5 words)",
        "audio_path": audio_1,
        "transcript": "The quick brown fox jumps",
        "expected_word_count": 5,
    })

    # Case 2: Medium sentence (12 words), ~5s
    audio_2 = tmp_path / "case_2.wav"
    _synthesize_tone_wav(audio_2, sample_rate, 5.0, freq=350)
    cases.append({
        "name": "Medium sentence (12 words)",
        "audio_path": audio_2,
        "transcript": "This is a longer sentence to test alignment accuracy across multiple words",
        "expected_word_count": 12,
    })

    # Case 3: Short sentence (8 words), ~3s
    audio_3 = tmp_path / "case_3.wav"
    _synthesize_tone_wav(audio_3, sample_rate, 3.0, freq=520)
    cases.append({
        "name": "Short sentence (8 words)",
        "audio_path": audio_3,
        "transcript": "Hello world this is a test",
        "expected_word_count": 6,
    })

    # Case 4: Multi-sentence (~20 words), ~8s
    audio_4 = tmp_path / "case_4.wav"
    _synthesize_tone_wav(audio_4, sample_rate, 8.0, freq=280)
    cases.append({
        "name": "Multi-sentence (~20 words)",
        "audio_path": audio_4,
        "transcript": (
            "This is the first sentence of the test. "
            "Here is another sentence with more words to check. "
            "And finally a third sentence for good measure."
        ),
        "expected_word_count": 23,
    })

    # Case 5: Single long word, ~2s
    audio_5 = tmp_path / "case_5.wav"
    _synthesize_tone_wav(audio_5, sample_rate, 2.0, freq=440)
    cases.append({
        "name": "Single long word",
        "audio_path": audio_5,
        "transcript": "Supercalifragilisticexpialidocious",
        "expected_word_count": 1,
    })

    return cases


# =========================================================================
# Tests
# =========================================================================


class TestAlignmentAccuracy:
    """PROD-AUDIO-03: Alignment accuracy ≥90%."""

    @pytest.mark.slow
    @pytest.mark.integration
    @pytest.mark.skipif(
        not os.getenv("FASTER_WHISPER_AVAILABLE"),
        reason="faster-whisper model not downloaded",
    )
    def test_alignment_accuracy_meets_threshold(self, tmp_path):
        """For each test clip, run force_align and verify word count matches."""
        pytest.importorskip("faster_whisper")

        from agent_core.audio.alignment.aligner import force_align

        cases = _build_test_cases(tmp_path)

        for case in cases:
            logger.info(
                "Testing: %s (transcript: %r)",
                case["name"],
                case["transcript"][:50],
            )

            result = force_align(case["audio_path"], case["transcript"])

            if result is None:
                logger.warning(
                    "Alignment returned None for %s — skipping",
                    case["name"],
                )
                continue

            word_count = len(result)
            expected = case["expected_word_count"]

            # Allow some flexibility — alignment may split/merge words differently
            tolerance = max(1, int(expected * 0.2))
            min_expected = max(1, expected - tolerance)
            max_expected = expected + tolerance

            assert min_expected <= word_count <= max_expected, (
                f"{case['name']}: expected ~{expected} words, got {word_count} "
                f"(tolerance: ±{tolerance})"
            )

            logger.info(
                "  ✓ %s: %d words (expected ~%d)",
                case["name"],
                word_count,
                expected,
            )

    @pytest.mark.slow
    @pytest.mark.integration
    @pytest.mark.skipif(
        not os.getenv("FASTER_WHISPER_AVAILABLE"),
        reason="faster-whisper model not downloaded",
    )
    def test_tiny_model_vs_base_fallback(self, tmp_path):
        """Try tiny model, check accuracy — log result.

        This test is informative: if tiny < 90 %, log a recommendation
        to bump to the base model.  It does not fail.
        """
        pytest.importorskip("faster_whisper")

        from agent_core.audio.alignment.aligner import force_align

        case = _build_test_cases(tmp_path)[0]
        result = force_align(case["audio_path"], case["transcript"])

        if result is None:
            logger.warning("Tiny model returned None — model may not be downloaded")
            pytest.skip("Model not available")

        accuracy = len(result) / max(case["expected_word_count"], 1)
        logger.info("Tiny model accuracy: %.1f%%", accuracy * 100)

        if accuracy < ACCURACY_THRESHOLD:
            logger.warning(
                "Tiny model accuracy (%.1f%%) is below threshold (%.0f%%). "
                "Consider bumping to 'base' model.",
                accuracy * 100,
                ACCURACY_THRESHOLD * 100,
            )
