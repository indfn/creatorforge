"""
Fallback chain orchestrator — tries TTS providers in order until one succeeds.

Follows the try-first-then-fallback pattern from ``metadata.py`` (lines 443-460).
Providers are registered in the ``PROVIDERS`` dict at module level for easy
extension. The ``_load_tts_config()`` helper reads TTS configuration from the
channel's ``channel_config.json``.
"""

import json
import logging
import re
from pathlib import Path
from typing import Optional

from agent_core.audio.tts.base import BaseTTSProvider, TTSResult
from agent_core.audio.tts.custom_provider import CustomTTSProvider
from agent_core.audio.tts.edge_provider import EdgeTTSProvider
from agent_core.audio.tts.gemini_provider import GeminiTTSProvider
from agent_core.audio.tts.google_cloud_provider import GoogleCloudTTSProvider

logger = logging.getLogger(__name__)

# Registry of all available TTS providers — keys match the ``provider`` field
# in ``channel_config.json`` and the ``fallback_chain`` list.
PROVIDERS: dict[str, type[BaseTTSProvider]] = {
    "custom": CustomTTSProvider,
    "gemini": GeminiTTSProvider,
    "google_cloud": GoogleCloudTTSProvider,
    "edge": EdgeTTSProvider,
}

# Default fallback order — used when no chain is specified in config.
DEFAULT_FALLBACK_CHAIN = ["custom", "gemini", "google_cloud", "edge"]


class FallbackChain:
    """Orchestrates TTS provider fallback.

    Tries each provider in ``chain`` order. Returns the first successful result
    or ``None`` if all providers fail (never raises).

    Usage::

        chain = FallbackChain()
        result = chain.generate("Hello world", {"voice": "Zephyr"})
    """

    def __init__(
        self,
        chain: Optional[list[str]] = None,
        provider_configs: Optional[dict] = None,
    ):
        """Initialise the fallback chain.

        Args:
            chain: Ordered list of provider names to try. Defaults to
                ``DEFAULT_FALLBACK_CHAIN`` (gemini → google_cloud → edge).
            provider_configs: Per-provider initialisation kwargs dict, keyed by
                provider name. E.g. ``{"google_cloud": {"credentials_path": "..."}}``.
        """
        self.chain = list(chain) if chain else list(DEFAULT_FALLBACK_CHAIN)
        self.provider_configs = provider_configs or {}

    def generate(self, text: str, voice_config: dict) -> Optional[TTSResult]:
        """Attempt TTS synthesis across the provider chain.

        Args:
            text: Plain text to synthesise.
            voice_config: Voice configuration dict passed to each provider.

        Returns:
            ``TTSResult`` from the first successful provider, or ``None`` if
            all providers in the chain failed.
        """
        for provider_name in self.chain:
            provider_cls = PROVIDERS.get(provider_name)
            if provider_cls is None:
                logger.warning(
                    "FallbackChain: unknown provider %r — skipping", provider_name
                )
                continue

            try:
                # Instantiate provider with its config (if any)
                kwargs = self.provider_configs.get(provider_name, {})
                provider = provider_cls(**kwargs)

                result = provider.generate(text, voice_config)
                if result is not None:
                    logger.info(
                        "FallbackChain: %s succeeded", provider_name
                    )
                    return result

                logger.warning(
                    "FallbackChain: %s returned None — trying next",
                    provider_name,
                )
            except Exception as e:
                logger.warning(
                    "FallbackChain: %s raised %s — trying next",
                    provider_name,
                    e,
                )

        logger.error("FallbackChain: all providers exhausted — no audio generated")
        return None


# ====== Config Helpers ======


def _project_root() -> Path:
    """Resolve the project root directory (parent of ``agent_core/``)."""
    return Path(__file__).resolve().parent.parent.parent.parent


def _validate_channel(channel: str) -> None:
    """Validate channel name to prevent path traversal.

    Raises:
        ValueError: If channel name contains invalid characters.
    """
    if not re.match(r"^[A-Za-z0-9_-]+$", channel):
        raise ValueError(
            f"Invalid channel name: {channel!r}. "
            "Only letters, numbers, hyphens, underscores allowed."
        )


def _channel_config_path(channel: str) -> Path:
    """Resolve the per-channel config file path."""
    _validate_channel(channel)
    return _project_root() / "channels" / channel / "channel_config.json"


def _load_channel_config(channel: str) -> dict:
    """Load the per-channel configuration JSON, returning empty dict on failure."""
    config_path = _channel_config_path(channel)
    if not config_path.exists():
        logger.warning("Channel config not found: %s", config_path)
        return {}
    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, ValueError) as e:
        logger.warning("Failed to parse channel config %s: %s", config_path, e)
        return {}


def _load_tts_config(channel: str) -> tuple[list[str], dict, dict]:
    """Load TTS configuration from a channel's ``channel_config.json``.

    Reads the ``production.tts`` section and returns the fallback chain,
    per-provider init configs, and the voice config dict.

    Args:
        channel: Channel name (e.g. ``"ChannelA"``).

    Returns:
        Tuple of ``(fallback_chain, provider_configs, voice_config)``.
        Returns defaults on any failure — never raises.
    """
    try:
        config = _load_channel_config(channel)
        tts_config = config.get("production", {}).get("tts", {})

        # Fallback chain from config or default
        fallback_chain = tts_config.get(
            "fallback_chain", list(DEFAULT_FALLBACK_CHAIN)
        )

        # Per-provider init configs (empty for now — no provider needs special
        # per-channel config beyond what's already in env vars / ADC).
        provider_configs: dict = {}

        # Provider-specific voice config from characters section
        voice_config: dict = {}
        characters = tts_config.get("characters", {})
        if "main" in characters:
            voice_config = characters["main"]
        elif characters:
            # Use the first character entry
            voice_config = next(iter(characters.values()))

        logger.info(
            "Loaded TTS config for channel %s: chain=%s, voice=%s",
            channel,
            fallback_chain,
            voice_config.get("voice", "default"),
        )
        return fallback_chain, provider_configs, voice_config

    except Exception as e:
        logger.warning(
            "Failed to load TTS config for channel %s: %s — using defaults",
            channel,
            e,
        )
        return list(DEFAULT_FALLBACK_CHAIN), {}, {}
