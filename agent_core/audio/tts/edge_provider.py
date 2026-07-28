"""
Edge TTS provider — uses the edge-tts library (Microsoft Edge TTS, free).

SSML injection is prevented by stripping all XML/HTML tags from input text
(T-09-01-01). No credentials are needed. This provider uses edge-tts's
``save_sync()`` convenience method which handles the async event loop
internally (per Pitfall 3). Returns ``None`` on failure — never raises.
"""

import logging
import os
from pathlib import Path
from typing import Optional

from agent_core.audio.tts.base import BaseTTSProvider, TTSResult, strip_ssml

logger = logging.getLogger(__name__)


class EdgeTTSProvider(BaseTTSProvider):
    """TTS provider using Microsoft Edge TTS (edge-tts library).

    No credentials required. Uses edge-tts's synchronous convenience wrapper
    ``save_sync()`` to write MP3 audio directly to a file, then converts to
    WAV via the built-in pydub decoder or returns the MP3 as-is depending on
    the configured output format.
    """

    def __init__(self):
        logger.info("EdgeTTSProvider initialised")

    def generate(self, text: str, voice_config: dict) -> Optional[TTSResult]:
        """Synthesize speech via Microsoft Edge TTS.

        Args:
            text: Plain text (XML/SSML tags stripped automatically).
            voice_config: Dict with optional ``voice``, ``rate``, ``pitch`` keys.

        Returns:
            TTSResult with path to a WAV file, or ``None`` on failure.
        """
        try:
            import edge_tts

            # SSML injection protection (T-09-01-01)
            safe_text = strip_ssml(text)
            if not safe_text.strip():
                logger.warning("EdgeTTSProvider: empty text after SSML strip")
                return None

            voice = voice_config.get("voice", "en-US-AriaNeural")
            rate = voice_config.get("rate", "+0%")
            pitch = voice_config.get("pitch", "+0Hz")

            communicate = edge_tts.Communicate(
                text=safe_text,
                voice=voice,
                rate=rate,
                pitch=pitch,
            )

            # Write to temp path via save_sync (handles async internally)
            import tempfile

            tmp_mp3 = tempfile.NamedTemporaryFile(
                suffix=".mp3", delete=False
            )
            tmp_mp3_path = tmp_mp3.name
            tmp_mp3.close()

            communicate.save_sync(tmp_mp3_path)

            # Convert MP3 to WAV for compatibility with the pipeline
            wav_bytes, sample_rate, duration = _mp3_to_wav(tmp_mp3_path)

            # Clean up temp MP3
            os.unlink(tmp_mp3_path)

            import tempfile as tf

            tmp_wav = tf.NamedTemporaryFile(suffix=".wav", delete=False)
            tmp_wav.write(wav_bytes)
            tmp_wav.close()

            result = TTSResult(
                audio_path=tmp_wav.name,
                duration_seconds=duration,
                format="wav",
            )

            logger.info(
                "EdgeTTSProvider: synthesised %.1fs of audio", duration
            )
            return result

        except Exception as e:
            logger.warning("EdgeTTSProvider.generate failed: %s", e)
            return None


def _mp3_to_wav(mp3_path: str) -> tuple[bytes, int, float]:
    """Convert an MP3 file to WAV bytes using pydub (preferred) or ffmpeg fallback.

    Returns:
        Tuple of (wav_bytes, sample_rate, duration_seconds).
    """
    try:
        from pydub import AudioSegment

        audio = AudioSegment.from_mp3(mp3_path)
        sample_rate = audio.frame_rate
        duration = len(audio) / 1000.0  # milliseconds → seconds
        buf = io.BytesIO() if "io" in dir() else __import__("io").BytesIO()
        import io as _io

        buf = _io.BytesIO()
        audio.export(buf, format="wav")
        return buf.getvalue(), sample_rate, duration
    except ImportError:
        pass  # Fall through to ffmpeg

    # Fallback: ffmpeg subprocess
    import subprocess as sp
    import tempfile
    import io

    tmp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp_wav_path = tmp_wav.name
    tmp_wav.close()

    try:
        sp.run(
            ["ffmpeg", "-y", "-i", mp3_path, "-acodec", "pcm_s16le",
             "-ar", "24000", "-ac", "1", tmp_wav_path],
            capture_output=True,
            check=True,
        )
        wav_bytes = Path(tmp_wav_path).read_bytes()
        # Estimate duration from file size (16-bit mono PCM)
        data_size = len(wav_bytes) - 44  # skip WAV header
        sample_rate = 24000
        duration = data_size / (sample_rate * 2)
        os.unlink(tmp_wav_path)
        return wav_bytes, sample_rate, duration
    except Exception as e:
        logger.warning("EdgeTTSProvider ffmpeg conversion failed: %s", e)
        raise  # Let caller handle via None return
    finally:
        if os.path.exists(tmp_wav_path):
            try:
                os.unlink(tmp_wav_path)
            except OSError:
                pass
