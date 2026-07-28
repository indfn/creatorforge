"""
Gemini TTS provider — uses the google-genai SDK to call Gemini 3.1 Flash TTS Preview.

SSML injection is prevented by stripping all XML/HTML tags from input text
before passing it to the API (T-09-01-01). API keys are never included in
log messages (T-09-01-02). Retry with exponential backoff handles the API's
Preview status (known 500 errors per Pitfall 4; T-09-01-03).
"""

import io
import logging
import os
import wave
from typing import Optional

from agent_core.audio.tts.base import BaseTTSProvider, TTSResult, strip_ssml
from agent_core.recon.utils.retry import retry_with_backoff

logger = logging.getLogger(__name__)


class GeminiTTSProvider(BaseTTSProvider):
    """TTS provider using the Google Gemini API (google-genai SDK).

    Requires the ``GEMINI_API_KEY`` environment variable to be set.
    Falls back to ``None`` return on all failures — never raises.
    """

    def __init__(self, api_key: Optional[str] = None):
        key = api_key or os.getenv("GEMINI_API_KEY")
        if not key:
            self.client = None
            logger.warning(
                "GeminiTTSProvider: No GEMINI_API_KEY set — provider disabled"
            )
            return

        try:
            import google.genai as genai

            self.client = genai.Client(api_key=key)
            logger.info("GeminiTTSProvider initialised")
        except Exception as e:
            self.client = None
            logger.warning("GeminiTTSProvider init failed: %s", e)

    def generate(self, text: str, voice_config: dict) -> Optional[TTSResult]:
        """Synthesize speech via Gemini 3.1 Flash TTS Preview.

        Args:
            text: Plain text (XML/SSML tags stripped automatically).
            voice_config: Dict with optional ``voice`` key.

        Returns:
            TTSResult with path to a WAV file, or ``None`` on failure.
        """
        if self.client is None:
            logger.error("GeminiTTSProvider: client not available")
            return None

        try:
            # SSML injection protection (T-09-01-01)
            safe_text = strip_ssml(text)
            if not safe_text.strip():
                logger.warning("GeminiTTSProvider: empty text after SSML strip")
                return None

            voice = voice_config.get("voice", "Zephyr")

            response = self._call_api(safe_text, voice)
            if response is None:
                return None

            # Decode base64 audio data from the response
            audio_bytes = _extract_audio_bytes(response)
            if audio_bytes is None:
                return None

            sample_rate = voice_config.get("sample_rate", 24000)
            # Write WAV with proper header
            buf = io.BytesIO()
            with wave.Wave_write(buf) as w:
                w.setnchannels(1)
                w.setsampwidth(2)  # 16-bit PCM
                w.setframerate(sample_rate)
                w.writeframes(audio_bytes)

            wav_bytes = buf.getvalue()
            duration = len(audio_bytes) / (sample_rate * 2)  # mono 16-bit

            # Write to a temp file — generate_from_text will move it
            import tempfile

            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            tmp.write(wav_bytes)
            tmp.close()

            result = TTSResult(
                audio_path=tmp.name,
                duration_seconds=duration,
                format="wav",
            )

            logger.info(
                "GeminiTTSProvider: synthesised %.1fs of audio", duration
            )
            return result

        except Exception as e:
            logger.warning("GeminiTTSProvider.generate failed: %s", e)
            return None

    @retry_with_backoff(max_attempts=3, category="TTS_GEMINI")
    def _call_api(self, text: str, voice: str) -> Optional[object]:
        """Internal API call with retry (T-09-01-03).

        Returns the raw response object from google.genai, or ``None``.
        """
        try:
            import google.genai as genai

            response = self.client.models.generate_content(
                model="gemini-3.1-flash-tts-preview",
                contents=text,
                config=genai.types.GenerateContentConfig(
                    speech_config=genai.types.SpeechConfig(
                        voice_config=genai.types.VoiceConfig(
                            prebuilt_voice_config=genai.types.PrebuiltVoiceConfig(
                                voice_name=voice,
                            ),
                        ),
                    ),
                ),
            )
            return response
        except Exception as e:
            logger.warning("GeminiTTSProvider._call_api attempt failed: %s", e)
            return None


def _extract_audio_bytes(response: object) -> Optional[bytes]:
    """Extract raw PCM16 audio bytes from a Gemini TTS API response.

    Handles both the base64-encoded ``audio_data`` field and the
    newer ``candidates[0].content.parts[0].inline_data.data`` path.
    """
    try:
        # Primary path: response.data / response.audio_data
        if hasattr(response, "data") and response.data:
            import base64
            return base64.b64decode(response.data)

        if hasattr(response, "audio_data") and response.audio_data:
            import base64
            return base64.b64decode(response.audio_data)

        # Fallback: candidates[0].content.parts[0].inline_data
        if (
            hasattr(response, "candidates")
            and response.candidates
            and response.candidates[0].content.parts
        ):
            part = response.candidates[0].content.parts[0]
            if hasattr(part, "inline_data") and part.inline_data:
                return part.inline_data.data

        logger.warning(
            "GeminiTTSProvider: could not extract audio from response structure"
        )
        return None
    except Exception as e:
        logger.warning("GeminiTTSProvider: audio extraction error: %s", e)
        return None
