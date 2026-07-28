"""
Shared test fixtures for audio module tests.

Fixtures in this conftest are re-exported from ``tests/test_audio/conftest.py``
for discoverability.  Tests should import directly from that module or request
fixtures by name (pytest resolves conftest files automatically per-directory).

Usage::

    def test_something(sample_word_timestamps):
        ...  # pytest discovers the fixture from test_audio/conftest.py
"""

import json
import math
import struct
import wave
from pathlib import Path

import pytest


# =========================================================================
# Re-exported fixtures
# =========================================================================
# These fixtures are defined in tests/test_audio/conftest.py and are
# accessible from test_audio/ tests directly.  We keep the fixture
# declarations here as documentation and for any future agents/ tests.

# sample_word_timestamps  — 10 mock word timestamps
# mock_scene_data         — List of 3 mock scene dicts
# mock_whisper_model      — Mocked faster-whisper model
# sample_scene_script     — Temp scene script text file


# =========================================================================
# Synthetic audio fixture
# =========================================================================


@pytest.fixture
def temp_audio_path(tmp_path):
    """Create a synthetic ~1 s 16 kHz mono WAV file for alignment tests.

    Generates a 440 Hz sine wave at 16 kHz sample rate, 16-bit PCM.
    """
    audio_file = tmp_path / "test_audio.wav"
    sample_rate = 16000
    duration = 1.0
    num_samples = int(sample_rate * duration)

    samples = []
    for i in range(num_samples):
        t = i / sample_rate
        sample = int(16000 * 0.5 * math.sin(2 * math.pi * 440 * t))
        samples.append(sample)

    with wave.open(str(audio_file), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        for s in samples:
            wf.writeframes(struct.pack("<h", s))

    return audio_file


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
