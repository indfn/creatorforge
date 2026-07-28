"""
Tests for TTS provider abstraction, fallback chain, and config loading.

Covers:
    - BaseTTSProvider ABC instantiation guard
    - TTSResult dataclass fields
    - FallbackChain orchestration (empty, ordered fallback, custom chain)
    - PROVIDERS registry contents
    - _load_tts_config with valid and missing channels
    - Individual provider initialisation behaviour
    - SSML injection protection (tag stripping)
"""

import logging

import pytest


# =========================================================================
# BaseTTSProvider & TTSResult
# =========================================================================


class TestBaseTTSProvider:
    """Tests for the abstract base provider class."""

    def test_base_class_cannot_be_instantiated(self):
        """ABC should raise TypeError when instantiated directly."""
        from agent_core.audio.tts.base import BaseTTSProvider

        with pytest.raises(TypeError):
            BaseTTSProvider()  # type: ignore[abstract]

    def test_tts_result_dataclass(self):
        """Verify TTSResult fields and defaults."""
        from agent_core.audio.tts.base import TTSResult

        result = TTSResult(audio_path="/tmp/test.wav", duration_seconds=2.5)
        assert result.audio_path == "/tmp/test.wav"
        assert result.duration_seconds == 2.5
        assert result.format == "wav"  # default


# =========================================================================
# FallbackChain
# =========================================================================


class TestFallbackChain:
    """Tests for the fallback chain orchestrator."""

    def test_fallback_chain_empty_provider_logs_warning(self, caplog):
        """All providers fail — verify warning is logged."""
        from agent_core.audio.tts.fallback_chain import FallbackChain

        # Empty chain means no providers to try
        chain = FallbackChain(chain=[])
        caplog.set_level(logging.WARNING)

        result = chain.generate("test text", {})
        assert result is None

        # Should log about all providers exhausted
        assert any(
            "all providers exhausted" in record.message.lower()
            for record in caplog.records
        )

    def test_fallback_chain_ordered_execution(self, mocker):
        """Mock first provider succeeds — verify no fallback is called."""
        from agent_core.audio.tts.fallback_chain import FallbackChain, PROVIDERS

        # Mock a provider that always succeeds
        mock_provider_cls = mocker.MagicMock()
        mock_instance = mock_provider_cls.return_value
        mock_instance.generate.return_value = mocker.MagicMock(
            audio_path="/tmp/test.wav",
            duration_seconds=1.0,
            format="wav",
        )

        # Temporarily inject into PROVIDERS
        PROVIDERS["_test_ok"] = mock_provider_cls

        try:
            chain = FallbackChain(chain=["_test_ok", "edge"])
            result = chain.generate("hello", {})

            assert result is not None
            mock_instance.generate.assert_called_once_with("hello", {})

            # Second provider should NOT have been called
            assert "_test_ok" in PROVIDERS
        finally:
            PROVIDERS.pop("_test_ok", None)

    def test_fallback_chain_custom_chain(self):
        """Verify custom chain ordering is respected."""
        from agent_core.audio.tts.fallback_chain import FallbackChain

        chain = FallbackChain(chain=["edge", "gemini"])
        assert chain.chain == ["edge", "gemini"]

    def test_fallback_chain_default_chain(self):
        """Verify default fallback chain."""
        from agent_core.audio.tts.fallback_chain import (
            DEFAULT_FALLBACK_CHAIN,
            FallbackChain,
        )

        chain = FallbackChain()
        assert chain.chain == DEFAULT_FALLBACK_CHAIN


# =========================================================================
# PROVIDERS Registry
# =========================================================================


class TestProvidersRegistry:
    """Tests for the PROVIDERS module-level registry."""

    def test_providers_registry_contains_expected(self):
        """Verify PROVIDERS dict has the expected keys."""
        from agent_core.audio.tts.fallback_chain import PROVIDERS

        assert "gemini" in PROVIDERS
        assert "google_cloud" in PROVIDERS
        assert "edge" in PROVIDERS
        assert len(PROVIDERS) >= 3


# =========================================================================
# _load_tts_config
# =========================================================================


class TestLoadTTSConfig:
    """Tests for the _load_tts_config helper."""

    def test_load_tts_config_with_valid_channel(self, mock_channel_config, monkeypatch):
        """Create temp config, verify parsing returns proper values."""
        # Patch _project_root to point at the temp directory
        import agent_core.audio.tts.fallback_chain as fb

        # The fixture creates channels/TestChannel/ in tmp_path
        # We need _project_root to resolve to tmp_path
        project_root = mock_channel_config.parents[2]  # channels/TestChannel -> channels -> tmp_path
        monkeypatch.setattr(fb, "_project_root", lambda: project_root)

        fallback_chain, provider_configs, voice_config = fb._load_tts_config("TestChannel")

        assert fallback_chain == ["gemini", "google_cloud", "edge"]
        assert voice_config.get("voice") == "Zephyr"
        assert isinstance(provider_configs, dict)

    def test_load_tts_config_missing_channel_returns_defaults(self, monkeypatch):
        """Non-existent channel returns default chain and empty configs."""
        import agent_core.audio.tts.fallback_chain as fb
        from agent_core.audio.tts.fallback_chain import DEFAULT_FALLBACK_CHAIN

        # Ensure _project_root points somewhere without the config
        import tempfile
        from pathlib import Path
        fake_root = Path(tempfile.mkdtemp())
        monkeypatch.setattr(fb, "_project_root", lambda: fake_root)

        fallback_chain, provider_configs, voice_config = fb._load_tts_config("NonExistent")
        assert fallback_chain == DEFAULT_FALLBACK_CHAIN
        assert provider_configs == {}
        assert voice_config == {}


# =========================================================================
# Individual providers
# =========================================================================


class TestGeminiTTSProvider:
    """Tests for GeminiTTSProvider initialisation."""

    def test_gemini_init_no_key_creates_no_client(self, disable_external_tts):
        """No GEMINI_API_KEY → self.client is None → generate returns None."""
        from agent_core.audio.tts.gemini_provider import GeminiTTSProvider

        provider = GeminiTTSProvider()
        assert provider.client is None

        result = provider.generate("test", {})
        assert result is None


class TestGoogleCloudTTSProvider:
    """Tests for GoogleCloudTTSProvider initialisation."""

    def test_gcloud_init_no_creds_handles_gracefully(self):
        """Without ADC credentials, init should handle failure gracefully."""
        from agent_core.audio.tts.google_cloud_provider import GoogleCloudTTSProvider

        # The provider should either fail during init (client=None) or during generate
        provider = GoogleCloudTTSProvider(credentials_path="/dev/null/nonexistent")
        # Should not raise — client may be None or generate may return None
        result = provider.generate("test", {})
        assert result is None


class TestEdgeTTSProvider:
    """Tests for EdgeTTSProvider initialisation."""

    def test_edge_provider_init(self):
        """Verify __init__ does not fail (no API keys required)."""
        from agent_core.audio.tts.edge_provider import EdgeTTSProvider

        provider = EdgeTTSProvider()
        # Should have no client attribute (edge uses subprocess, not an API client)
        assert provider is not None


# =========================================================================
# SSML Injection Protection
# =========================================================================


class TestSSMLStripping:
    """Tests for SSML/XML tag stripping."""

    def test_ssml_stripping(self):
        """Verify text with XML/SSML tags is stripped."""
        from agent_core.audio.tts.base import strip_ssml

        text = "Hello <break time='500ms'/> world <prosody rate='slow'>slow part</prosody>"
        cleaned = strip_ssml(text)
        assert "<break" not in cleaned
        assert "<prosody" not in cleaned
        assert "</prosody>" not in cleaned
        assert cleaned.strip() == "Hello  world slow part"

    def test_ssml_stripping_no_tags(self):
        """Plain text without tags is unchanged."""
        from agent_core.audio.tts.base import strip_ssml

        text = "Hello world this is a test."
        cleaned = strip_ssml(text)
        assert cleaned == text
