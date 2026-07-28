"""TTS provider abstraction — multi-provider fallback chain with BaseTTSProvider interface."""

from agent_core.audio.tts.base import BaseTTSProvider, TTSResult
from agent_core.audio.tts.custom_provider import CustomTTSProvider
from agent_core.audio.tts.gemini_provider import GeminiTTSProvider
from agent_core.audio.tts.google_cloud_provider import GoogleCloudTTSProvider
from agent_core.audio.tts.edge_provider import EdgeTTSProvider
from agent_core.audio.tts.fallback_chain import (
    DEFAULT_FALLBACK_CHAIN,
    PROVIDERS,
    FallbackChain,
    _load_tts_config,
)

__all__ = [
    "BaseTTSProvider",
    "TTSResult",
    "CustomTTSProvider",
    "GeminiTTSProvider",
    "GoogleCloudTTSProvider",
    "EdgeTTSProvider",
    "FallbackChain",
    "PROVIDERS",
    "DEFAULT_FALLBACK_CHAIN",
    "_load_tts_config",
]
