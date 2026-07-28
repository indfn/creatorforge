"""
Audio-specific test fixtures and mocks.

Provides fixtures for mocking the faster-whisper model (``mock_whisper_model``),
shared test data (``sample_word_timestamps``, ``mock_scene_data``), mock channel
config, TTS isolation, and sample scene scripts for integration tests.
"""

import json
import math
import struct
import wave
from pathlib import Path

import pytest


# =========================================================================
# Shared test data
# =========================================================================


@pytest.fixture
def sample_word_timestamps():
    """Return a list of 10 mock word timestamps for subtitle/alignment tests.

    Each word starts 300 ms apart with 250 ms duration, giving a 50 ms gap
    between consecutive words — well under the 500 ms pause threshold.
    """
    words = []
    for i, word in enumerate([
        "the", "quick", "brown", "fox", "jumps",
        "over", "the", "lazy", "dog", "now",
    ]):
        words.append({
            "word": word,
            "start": round(i * 0.3, 3),
            "end": round((i * 0.3) + 0.25, 3),
            "probability": 0.95,
        })
    return words


@pytest.fixture
def mock_scene_data():
    """Return a list of 3 mock scene dicts."""
    return [
        {"scene_id": "scene_01", "scene_number": 1, "text": "Hello world. This is scene one."},
        {"scene_id": "scene_02", "scene_number": 2, "text": "This is scene two with more content for testing."},
        {"scene_id": "scene_03", "scene_number": 3, "text": "Scene three the final scene."},
    ]


# =========================================================================
# Mock faster-whisper model
# =========================================================================


@pytest.fixture
def mock_whisper_model(mocker):
    """Mock faster-whisper ``WhisperModel`` via the module-level cache.

    Instead of patching ``faster_whisper.WhisperModel`` (which may not be
    installed), this fixture directly sets ``aligner._whisper_model`` to a
    mock object whose ``transcribe()`` method returns known word-level
    timestamps (5 words across 2 segments).
    """
    import agent_core.audio.alignment.aligner as aligner

    class MockWord:
        def __init__(self, word, start, end, probability):
            self.word = word
            self.start = start
            self.end = end
            self.probability = probability

    class MockSegment:
        def __init__(self, words, avg_logprob=0.0):
            self.words = words
            self.avg_logprob = avg_logprob

    seg1_words = [
        MockWord("Hello", 0.0, 0.3, 0.95),
        MockWord("world", 0.35, 0.6, 0.97),
        MockWord("this", 0.65, 0.85, 0.94),
    ]
    seg2_words = [
        MockWord("is", 0.9, 1.05, 0.96),
        MockWord("test", 1.1, 1.4, 0.93),
    ]
    segments = [MockSegment(seg1_words), MockSegment(seg2_words)]

    mock_instance = mocker.MagicMock()
    mock_instance.transcribe.return_value = (iter(segments), None)
    aligner._whisper_model = mock_instance
    return mock_instance


# =========================================================================
# Sample scene script
# =========================================================================


@pytest.fixture
def sample_scene_script(tmp_path):
    """Create a temporary scene script text file."""
    script_file = tmp_path / "scene_01_script.txt"
    script_file.write_text("Hello world this is test", encoding="utf-8")
    return script_file


# =========================================================================
# Channel config fixture
# =========================================================================


@pytest.fixture
def mock_channel_config(tmp_path, monkeypatch):
    """Create a temporary ``channel_config.json`` in a temp ``channels/`` dir.

    Returns:
        ``Path`` to the created ``channel_config.json``.
    """
    channels_dir = tmp_path / "channels"
    channel_dir = channels_dir / "TestChannel"
    channel_dir.mkdir(parents=True)

    config = {
        "production": {
            "tts": {
                "provider": "gemini",
                "fallback_chain": ["gemini", "google_cloud", "edge"],
                "characters": {
                    "main": {
                        "voice": "Zephyr",
                        "style": "neutral",
                    },
                },
            },
        },
    }
    config_path = channel_dir / "channel_config.json"
    config_path.write_text(json.dumps(config, indent=2))

    return config_path


# =========================================================================
# TTS isolation fixture
# =========================================================================


@pytest.fixture
def disable_external_tts(monkeypatch):
    """Remove TTS API key environment variables so providers skip cleanly.

    After applying this fixture:
        - ``GeminiTTSProvider`` initialises with ``client=None``
        - ``GoogleCloudTTSProvider`` is unable to find ADC credentials
        - ``EdgeTTSProvider`` is unaffected (no key required)
    """
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/dev/null/nonexistent")
