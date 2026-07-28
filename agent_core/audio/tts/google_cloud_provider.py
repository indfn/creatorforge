"""
Google Cloud TTS provider — uses the google-cloud-texttospeech SDK.

SSML injection is prevented by stripping all XML/HTML tags from input text
(T-09-01-01). Credentials are resolved from the path provided at init or from
Application Default Credentials (ADC). The provider returns ``None`` on all
failures — never raises.
"""

import io
import logging
import os
import wave
from typing import Optional

from agent_core.audio.tts.base import BaseTTSProvider, TTSResult, strip_ssml
from agent_core.recon.utils.retry import retry_with_backoff

logger = logging.getLogger(__name__)


class GoogleCloudTTSProvider(BaseTTSProvider):
    """TTS provider using Google Cloud Text-to-Speech.

    Initialises from a service account JSON file path or falls back to
    Application Default Credentials (ADC). The provider returns ``None``
    on any failure — never raises.
    """

    def __init__(self, credentials_path: Optional[str] = None):
        try:
            import google.cloud.texttospeech as tts

            if credentials_path and os.path.isfile(credentials_path):
                from google.oauth2 import service_account

                credentials = service_account.Credentials.from_service_account_file(
                    credentials_path
                )
                self.client = tts.TextToSpeechClient(credentials=credentials)
                logger.info(
                    "GoogleCloudTTSProvider initialised with service account"
                )
            else:
                self.client = tts.TextToSpeechClient()
                logger.info(
                    "GoogleCloudTTSProvider initialised via ADC"
                )
        except Exception as e:
            self.client = None
            logger.warning("GoogleCloudTTSProvider init failed: %s", e)

    def generate(self, text: str, voice_config: dict) -> Optional[TTSResult]:
        """Synthesize speech via Google Cloud Text-to-Speech.

        Args:
            text: Plain text (XML/SSML tags stripped automatically).
            voice_config: Dict with optional ``language_code``, ``voice``, ``rate`` keys.

        Returns:
            TTSResult with path to a WAV file, or ``None`` on failure.
        """
        if self.client is None:
            logger.error("GoogleCloudTTSProvider: client not available")
            return None

        try:
            import google.cloud.texttospeech as tts

            # SSML injection protection (T-09-01-01)
            safe_text = strip_ssml(text)
            if not safe_text.strip():
                logger.warning(
                    "GoogleCloudTTSProvider: empty text after SSML strip"
                )
                return None

            synthesis_input = tts.SynthesisInput(text=safe_text)

            language_code = voice_config.get("language_code", "en-US")
            voice_name = voice_config.get("voice", "en-US-Neural2-A")
            voice_params = tts.VoiceSelectionParams(
                language_code=language_code,
                name=voice_name,
                ssml_gender=tts.SsmlVoiceGender.NEUTRAL,
            )

            speaking_rate = voice_config.get("rate", 1.0)
            audio_config = tts.AudioConfig(
                audio_encoding=tts.AudioEncoding.LINEAR16,
                speaking_rate=speaking_rate,
            )

            response = self._call_api(
                synthesis_input, voice_params, audio_config
            )
            if response is None:
                return None

            # Google Cloud returns raw PCM16 in response.audio_content
            pcm_bytes = response.audio_content
            sample_rate = voice_config.get("sample_rate", 24000)

            # Write WAV header + PCM data
            wav_bytes = _pcm_to_wav(pcm_bytes, sample_rate)
            duration = len(pcm_bytes) / (sample_rate * 2)  # mono 16-bit

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
                "GoogleCloudTTSProvider: synthesised %.1fs of audio",
                duration,
            )
            return result

        except Exception as e:
            logger.warning("GoogleCloudTTSProvider.generate failed: %s", e)
            return None

    @retry_with_backoff(max_attempts=3, category="TTS_GCLOUD")
    def _call_api(
        self,
        synthesis_input: object,
        voice_params: object,
        audio_config: object,
    ) -> Optional[object]:
        """Internal API call with retry for HTTP reliability."""
        try:
            response = self.client.synthesize_speech(
                input=synthesis_input,
                voice=voice_params,
                audio_config=audio_config,
            )
            return response
        except Exception as e:
            logger.warning(
                "GoogleCloudTTSProvider._call_api attempt failed: %s", e
            )
            return None


def _pcm_to_wav(pcm_bytes: bytes, sample_rate: int) -> bytes:
    """Wrap raw PCM16 mono audio data in a RIFF WAV header."""
    buf = io.BytesIO()
    with wave.Wave_write(buf) as w:
        w.setnchannels(1)
        w.setsampwidth(2)  # 16-bit
        w.setframerate(sample_rate)
        w.writeframes(pcm_bytes)
    return buf.getvalue()
