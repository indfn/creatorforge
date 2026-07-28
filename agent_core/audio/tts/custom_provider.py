"""
Custom TTS provider — calls the same TTS proxy API as ``generate.py``
via a direct ``synthesize()`` import (no subprocess overhead).

Provider in the fallback chain: ``custom → gemini → google_cloud → edge``.
"""

import logging
import os
import tempfile
import wave
from pathlib import Path
from typing import Optional

from agent_core.audio.tts.base import BaseTTSProvider, TTSResult, strip_ssml
from agent_core.audio.tts.generate import synthesize as _synthesize

logger = logging.getLogger(__name__)


class CustomTTSProvider(BaseTTSProvider):
    """TTS provider that calls the Gemini Flash TTS proxy API directly.

    Uses the same ``synthesize()`` function as the CLI script, imported
    directly — no subprocess, no temp script files.

    Requires:
        - ``TTS_API_KEY`` env var (or the API key fallback in ``generate.py``)
        - ``TTS_PROXY_URL`` env var (or the default proxy URL)
    """

    def __init__(self, api_key: Optional[str] = None, proxy_url: Optional[str] = None):
        self.api_key = api_key or os.getenv("TTS_API_KEY")
        self.proxy_url = proxy_url or os.getenv("TTS_PROXY_URL")

    def generate(self, text: str, voice_config: dict) -> Optional[TTSResult]:
        safe_text = strip_ssml(text)
        if not safe_text.strip():
            logger.warning("CustomTTSProvider: empty text after SSML strip")
            return None

        try:
            audio_bytes, _mime, ext = _synthesize(
                script_text=safe_text,
                voice=voice_config.get("voice", "Zephyr"),
                style=voice_config.get("style", "Vocal Smile"),
                pace=voice_config.get("pace", "Natural"),
                accent=voice_config.get("accent", "American (Gen)"),
                profile=voice_config.get("profile", "Warm and educational"),
                scene=voice_config.get("scene", "A quiet recording booth."),
                context=voice_config.get("context", "Neutral mood."),
                proxy_url=self.proxy_url,
                api_key=self.api_key,
            )
        except RuntimeError as e:
            logger.warning("CustomTTSProvider.synthesize failed: %s", e)
            return None

        tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
        tmp.write(audio_bytes)
        tmp.close()

        try:
            with wave.open(tmp.name, "rb") as wf:
                duration = wf.getnframes() / wf.getframerate()
        except wave.Error:
            duration = 0.0

        return TTSResult(
            audio_path=tmp.name,
            duration_seconds=duration,
            format=ext.lstrip("."),
        )
