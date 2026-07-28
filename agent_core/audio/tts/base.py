"""
Base TTS provider abstraction — defines the TTSResult dataclass and BaseTTSProvider contract.

All TTS providers inherit from BaseTTSProvider and implement the ``generate()``
method. The ``generate_from_text()`` concrete method handles file writing so
providers only need to return raw audio bytes.
"""

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# SSML/XML tag stripping pattern for injection protection (T-09-01-01)
_SSML_TAG_RE = re.compile(r"<[^>]+>")


def strip_ssml(text: str) -> str:
    """Strip XML/SSML tags from text to prevent SSML injection.

    Args:
        text: Input text that may contain XML/SSML tags.

    Returns:
        Tag-stripped text.
    """
    return _SSML_TAG_RE.sub("", text)


@dataclass
class TTSResult:
    """Result of a TTS synthesis call.

    Attributes:
        audio_path: Absolute path to the synthesized audio file on disk.
        duration_seconds: Total duration of the audio in seconds.
        format: Audio container format (default ``"wav"``).
    """

    audio_path: str
    duration_seconds: float
    format: str = "wav"


class BaseTTSProvider(ABC):
    """Abstract base class for all TTS providers.

    Subclasses must implement ``generate()`` to perform the actual synthesis.
    The concrete ``generate_from_text()`` method calls ``generate()`` and
    writes the result to a predictable path.
    """

    @abstractmethod
    def generate(self, text: str, voice_config: dict) -> Optional[TTSResult]:
        """Synthesize speech from text and return a TTSResult.

        Args:
            text: The plain text to synthesize (XML/SSML tags must already be stripped).
            voice_config: Provider-specific voice configuration dict (voice name, rate, pitch, etc.).

        Returns:
            TTSResult on success, or ``None`` on failure — never raises.
        """
        ...

    def generate_from_text(
        self,
        text: str,
        voice_config: dict,
        output_dir: str,
        scene_id: str,
    ) -> Optional[TTSResult]:
        """Synthesize speech and write audio to ``{output_dir}/{scene_id}_audio.wav``.

        This is the primary entry point used by the production pipeline. It delegates
        to ``generate()`` and persists the result to disk.

        Args:
            text: Plain text to synthesize.
            voice_config: Voice configuration dict.
            output_dir: Directory to write the audio file into.
            scene_id: Scene identifier used in the output filename.

        Returns:
            TTSResult with ``audio_path`` pointing to the written file, or ``None`` on failure.
        """
        try:
            result = self.generate(text, voice_config)
            if result is None:
                return None

            output_path = Path(output_dir) / f"{scene_id}_audio.wav"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(Path(result.audio_path).read_bytes())

            return TTSResult(
                audio_path=str(output_path.resolve()),
                duration_seconds=result.duration_seconds,
                format=result.format,
            )
        except Exception as e:
            logger.warning("generate_from_text failed for scene %s: %s", scene_id, e)
            return None
