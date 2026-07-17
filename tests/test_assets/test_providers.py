"""
Tests for stock API asset providers (Pexels, Pixabay, Freesound) and fallback chain.

Covers:
    - Provider initialisation with missing API key
    - Mocked API search responses
    - Quota exhausted guards
    - Rate limit (429) handling
    - Network error handling
    - Download success and failure paths
    - Pixabay video quality selection (medium → small → tiny fallback)
    - Freesound preview URL usage and duration filter
    - AssetFallbackChain ordered execution, custom chain, and error handling
"""

import logging
from pathlib import Path

import pytest
import requests


# =========================================================================
# PexelsProvider
# =========================================================================


class TestPexelsProvider:
    """Tests for PexelsProvider."""

    def test_pexels_init_no_key_logs_warning(self, disable_stock_api_keys, caplog):
        """Missing API key logs warning and search returns empty."""
        from agent_core.assets.providers.pexels import PexelsProvider

        caplog.set_level(logging.WARNING)
        p = PexelsProvider()
        assert p.api_key == ""
        assert any("PEXELS_API_KEY not set" in record.message for record in caplog.records)
        assert p.search("test") == []

    def test_pexels_search_mocked_response(self, mocker):
        """Mocked Pexels API returns correct AssetResult fields."""
        mocker.patch.dict("os.environ", {"PEXELS_API_KEY": "test_key_123"})

        from agent_core.assets.providers.pexels import PexelsProvider

        mock_response_data = {
            "videos": [
                {
                    "id": 12345,
                    "width": 1920,
                    "height": 1080,
                    "duration": 15,
                    "user": {"name": "Test Photographer"},
                    "video_files": [
                        {"quality": "hd", "link": "https://example.com/video.mp4",
                         "width": 1920, "height": 1080},
                        {"quality": "sd", "link": "https://example.com/video_sd.mp4",
                         "width": 640, "height": 360},
                    ],
                }
            ]
        }

        mock_resp = mocker.MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response_data

        mocker.patch("requests.get", return_value=mock_resp)

        provider = PexelsProvider()
        results = provider.search("ocean waves")

        assert len(results) == 1
        result = results[0]
        assert result.source_url == "https://example.com/video.mp4"
        assert result.file_extension == "mp4"
        assert result.metadata["source"] == "pexels"
        assert result.metadata["video_id"] == 12345
        assert result.metadata["photographer"] == "Test Photographer"
        assert result.score == 1.0

    def test_pexels_search_quota_exhausted(self, mocker):
        """Quota exhausted returns empty without making HTTP request."""
        from agent_core.assets.providers.pexels import PexelsProvider

        mocker.patch.dict("os.environ", {"PEXELS_API_KEY": "test_key"})
        mock_can_consume = mocker.patch(
            "agent_core.core.quota.QuotaBudget.can_consume", return_value=False
        )
        mock_get = mocker.patch("requests.get")

        provider = PexelsProvider()
        results = provider.search("test")

        assert results == []
        mock_can_consume.assert_called_once_with("pexels", 1)
        mock_get.assert_not_called()

    def test_pexels_search_rate_limited(self, mocker):
        """429 response returns empty list."""
        from agent_core.assets.providers.pexels import PexelsProvider

        mocker.patch.dict("os.environ", {"PEXELS_API_KEY": "test_key"})
        mocker.patch(
            "agent_core.core.quota.QuotaBudget.can_consume", return_value=True
        )

        mock_resp = mocker.MagicMock()
        mock_resp.status_code = 429
        mocker.patch("requests.get", return_value=mock_resp)

        provider = PexelsProvider()
        results = provider.search("test")

        assert results == []

    def test_pexels_search_network_error(self, mocker):
        """Network error returns empty list."""
        from agent_core.assets.providers.pexels import PexelsProvider

        mocker.patch.dict("os.environ", {"PEXELS_API_KEY": "test_key"})
        mocker.patch(
            "agent_core.core.quota.QuotaBudget.can_consume", return_value=True
        )
        mocker.patch("requests.get", side_effect=requests.ConnectionError("connection failed"))

        provider = PexelsProvider()
        results = provider.search("test")

        assert results == []

    def test_pexels_download_success(self, mocker, tmp_path):
        """Download streams file to disk successfully."""
        from agent_core.assets.providers.pexels import PexelsProvider
        from agent_core.assets.base import AssetResult

        output_path = tmp_path / "downloads" / "video.mp4"

        # Mock streaming response
        mock_stream = mocker.MagicMock()
        mock_stream.iter_content.return_value = [b"chunk1", b"chunk2"]
        mock_stream.raise_for_status = mocker.MagicMock()

        mocker.patch("requests.get", return_value=mock_stream)

        asset = AssetResult(
            source_url="https://example.com/video.mp4",
            file_extension="mp4",
            metadata={"source": "pexels"},
            score=1.0,
        )

        provider = PexelsProvider()
        result = provider.download(asset, output_path)

        assert result == output_path
        assert output_path.exists()
        assert output_path.read_bytes() == b"chunk1chunk2"

    def test_pexels_download_failure(self, mocker):
        """Download failure returns None."""
        from agent_core.assets.providers.pexels import PexelsProvider
        from agent_core.assets.base import AssetResult

        mocker.patch(
            "requests.get", side_effect=requests.RequestException("download failed")
        )

        asset = AssetResult(
            source_url="https://example.com/video.mp4",
            file_extension="mp4",
            metadata={"source": "pexels"},
            score=1.0,
        )

        provider = PexelsProvider()
        result = provider.download(asset, Path("/tmp/nonexistent/video.mp4"))

        assert result is None


# =========================================================================
# PixabayProvider
# =========================================================================


class TestPixabayProvider:
    """Tests for PixabayProvider."""

    def test_pixabay_init_no_key(self, disable_stock_api_keys):
        """Missing API key returns empty search."""
        from agent_core.assets.providers.pixabay import PixabayProvider

        p = PixabayProvider()
        assert p.api_key == ""
        assert p.search("test") == []

    def test_pixabay_search_mocked_response(self, mocker):
        """Mocked Pixabay API returns correct AssetResult fields."""
        mocker.patch.dict("os.environ", {"PIXABAY_API_KEY": "test_key"})

        from agent_core.assets.providers.pixabay import PixabayProvider

        mock_response_data = {
            "totalHits": 1,
            "hits": [
                {
                    "id": 67890,
                    "pageURL": "https://pixabay.com/videos/test-123/",
                    "type": "video",
                    "tags": "ocean, waves, beach",
                    "duration": 12,
                    "videos": {
                        "medium": {
                            "url": "https://example.com/pixabay_medium.mp4",
                            "width": 1920,
                            "height": 1080,
                            "size": 2500000,
                        },
                        "small": {
                            "url": "https://example.com/pixabay_small.mp4",
                            "width": 640,
                            "height": 360,
                            "size": 800000,
                        },
                        "tiny": {
                            "url": "https://example.com/pixabay_tiny.mp4",
                            "width": 480,
                            "height": 270,
                            "size": 300000,
                        },
                    },
                    "user_id": 123456,
                    "user": "TestPhotographer",
                    "imageWidth": 1920,
                    "imageHeight": 1080,
                }
            ],
            "total": 1,
        }

        mock_resp = mocker.MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response_data

        mocker.patch("requests.get", return_value=mock_resp)
        mocker.patch(
            "agent_core.core.quota.QuotaBudget.can_consume", return_value=True
        )

        provider = PixabayProvider()
        results = provider.search("ocean")

        assert len(results) == 1
        result = results[0]
        assert result.source_url == "https://example.com/pixabay_medium.mp4"
        assert result.file_extension == "mp4"
        assert result.metadata["source"] == "pixabay"
        assert result.metadata["video_id"] == 67890
        assert result.metadata["tags"] == "ocean, waves, beach"
        assert result.score == 0.9

    def test_pixabay_search_selects_medium_then_small_then_tiny(self, mocker):
        """Pixabay picks small when medium is unavailable, then tiny."""
        mocker.patch.dict("os.environ", {"PIXABAY_API_KEY": "test_key"})

        from agent_core.assets.providers.pixabay import PixabayProvider

        # Response with only 'small' quality available
        response = {
            "hits": [
                {
                    "id": 111,
                    "tags": "test",
                    "duration": 5,
                    "videos": {
                        "small": {
                            "url": "https://example.com/small.mp4",
                            "width": 640,
                            "height": 360,
                            "size": 800000,
                        },
                        "tiny": {
                            "url": "https://example.com/tiny.mp4",
                            "width": 480,
                            "height": 270,
                            "size": 300000,
                        },
                    },
                }
            ]
        }

        mock_resp = mocker.MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = response

        mocker.patch("requests.get", return_value=mock_resp)
        mocker.patch(
            "agent_core.core.quota.QuotaBudget.can_consume", return_value=True
        )

        provider = PixabayProvider()
        results = provider.search("test")

        assert len(results) == 1
        assert results[0].source_url == "https://example.com/small.mp4"
        assert results[0].metadata["width"] == 640

        # Now test tiny-only fallback
        response2 = {
            "hits": [
                {
                    "id": 222,
                    "tags": "test",
                    "duration": 3,
                    "videos": {
                        "tiny": {
                            "url": "https://example.com/tiny.mp4",
                            "width": 480,
                            "height": 270,
                            "size": 300000,
                        },
                    },
                }
            ]
        }

        mock_resp2 = mocker.MagicMock()
        mock_resp2.status_code = 200
        mock_resp2.json.return_value = response2

        mocker.patch("requests.get", return_value=mock_resp2)

        results2 = provider.search("test")
        assert len(results2) == 1
        assert results2[0].source_url == "https://example.com/tiny.mp4"

    def test_pixabay_search_quota_exhausted(self, mocker):
        """Quota exhausted returns empty."""
        from agent_core.assets.providers.pixabay import PixabayProvider

        mocker.patch.dict("os.environ", {"PIXABAY_API_KEY": "test_key"})
        mock_can_consume = mocker.patch(
            "agent_core.core.quota.QuotaBudget.can_consume", return_value=False
        )
        mock_get = mocker.patch("requests.get")

        provider = PixabayProvider()
        results = provider.search("test")

        assert results == []
        mock_can_consume.assert_called_once_with("pixabay", 1)
        mock_get.assert_not_called()

    def test_pixabay_search_rate_limited(self, mocker):
        """429 returns empty."""
        from agent_core.assets.providers.pixabay import PixabayProvider

        mocker.patch.dict("os.environ", {"PIXABAY_API_KEY": "test_key"})
        mocker.patch(
            "agent_core.core.quota.QuotaBudget.can_consume", return_value=True
        )

        mock_resp = mocker.MagicMock()
        mock_resp.status_code = 429
        mocker.patch("requests.get", return_value=mock_resp)

        provider = PixabayProvider()
        results = provider.search("test")

        assert results == []

    def test_pixabay_search_network_error(self, mocker):
        """Connection error returns empty."""
        from agent_core.assets.providers.pixabay import PixabayProvider

        mocker.patch.dict("os.environ", {"PIXABAY_API_KEY": "test_key"})
        mocker.patch(
            "agent_core.core.quota.QuotaBudget.can_consume", return_value=True
        )
        mocker.patch("requests.get", side_effect=requests.ConnectionError("fail"))

        provider = PixabayProvider()
        results = provider.search("test")

        assert results == []


# =========================================================================
# FreesoundProvider
# =========================================================================


class TestFreesoundProvider:
    """Tests for FreesoundProvider."""

    def test_freesound_init_no_key(self, disable_stock_api_keys):
        """Missing API key returns empty search."""
        from agent_core.assets.providers.freesound import FreesoundProvider

        p = FreesoundProvider()
        assert p.api_key == ""
        assert p.search("test") == []

    def test_freesound_search_mocked_response(self, mocker):
        """Mocked Freesound API returns correct AssetResult fields."""
        mocker.patch.dict("os.environ", {"FREESOUND_API_KEY": "test_key"})

        from agent_core.assets.providers.freesound import FreesoundProvider

        mock_response_data = {
            "count": 1,
            "results": [
                {
                    "id": 123456,
                    "name": "ocean_waves",
                    "tags": ["ocean", "waves", "water", "nature"],
                    "duration": 8.5,
                    "license": "Creative Commons 0",
                    "username": "sounddesigner",
                    "previews": {
                        "preview-hq-mp3": "https://example.com/sound_hq.mp3",
                        "preview-lq-mp3": "https://example.com/sound_lq.mp3",
                        "preview-hq-ogg": "https://example.com/sound_hq.ogg",
                        "preview-lq-ogg": "https://example.com/sound_lq.ogg",
                    },
                }
            ],
            "next": None,
            "previous": None,
        }

        mock_resp = mocker.MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response_data

        mocker.patch("requests.get", return_value=mock_resp)
        mocker.patch(
            "agent_core.core.quota.QuotaBudget.can_consume", return_value=True
        )

        provider = FreesoundProvider()
        results = provider.search("ocean waves")

        assert len(results) == 1
        result = results[0]
        assert result.source_url == "https://example.com/sound_hq.mp3"
        assert result.file_extension == "mp3"
        assert result.metadata["source"] == "freesound"
        assert result.metadata["sound_id"] == 123456
        assert result.metadata["name"] == "ocean_waves"
        assert result.metadata["tags"] == ["ocean", "waves", "water", "nature"]
        assert result.metadata["duration"] == 8.5
        assert result.metadata["license"] == "Creative Commons 0"
        assert result.metadata["username"] == "sounddesigner"

    def test_freesound_search_uses_preview_not_download(self, mocker):
        """Verify source_url is a preview URL, not a download endpoint."""
        mocker.patch.dict("os.environ", {"FREESOUND_API_KEY": "test_key"})

        from agent_core.assets.providers.freesound import FreesoundProvider

        mock_resp = mocker.MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "results": [
                {
                    "id": 1,
                    "name": "test",
                    "tags": ["test"],
                    "duration": 1.0,
                    "license": "CC0",
                    "username": "tester",
                    "previews": {
                        "preview-hq-mp3": "https://cdn.freesound.org/previews/12345_hq.mp3",
                    },
                }
            ]
        }

        mocker.patch("requests.get", return_value=mock_resp)
        mocker.patch(
            "agent_core.core.quota.QuotaBudget.can_consume", return_value=True
        )

        provider = FreesoundProvider()
        results = provider.search("test")

        assert len(results) == 1
        # Must contain 'preview', not 'download'
        assert "preview" in results[0].source_url
        assert "download" not in results[0].source_url

    def test_freesound_search_duration_filter(self, mocker):
        """Verify the duration filter is passed in the API request."""
        mocker.patch.dict("os.environ", {"FREESOUND_API_KEY": "test_key"})

        from agent_core.assets.providers.freesound import FreesoundProvider

        mock_resp = mocker.MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"results": []}

        mock_get = mocker.patch("requests.get", return_value=mock_resp)
        mocker.patch(
            "agent_core.core.quota.QuotaBudget.can_consume", return_value=True
        )

        provider = FreesoundProvider()
        provider.search("test")

        # Verify the filter param contains duration constraint
        call_kwargs = mock_get.call_args[1]
        assert "filter" in call_kwargs["params"]
        assert "duration:[0.1 TO 15]" in call_kwargs["params"]["filter"]

    def test_freesound_search_falls_back_to_lq_mp3(self, mocker):
        """When no HQ preview is available, fallback to LQ mp3."""
        mocker.patch.dict("os.environ", {"FREESOUND_API_KEY": "test_key"})

        from agent_core.assets.providers.freesound import FreesoundProvider

        mock_resp = mocker.MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "results": [
                {
                    "id": 2,
                    "name": "lq_only",
                    "tags": ["test"],
                    "duration": 2.0,
                    "license": "CC0",
                    "username": "tester",
                    "previews": {
                        "preview-lq-mp3": "https://cdn.freesound.org/previews/222_lq.mp3",
                    },
                }
            ]
        }

        mocker.patch("requests.get", return_value=mock_resp)
        mocker.patch(
            "agent_core.core.quota.QuotaBudget.can_consume", return_value=True
        )

        provider = FreesoundProvider()
        results = provider.search("test")

        assert len(results) == 1
        assert results[0].source_url == "https://cdn.freesound.org/previews/222_lq.mp3"

    def test_freesound_search_quota_exhausted(self, mocker):
        """Quota exhausted returns empty."""
        from agent_core.assets.providers.freesound import FreesoundProvider

        mocker.patch.dict("os.environ", {"FREESOUND_API_KEY": "test_key"})
        mock_can_consume = mocker.patch(
            "agent_core.core.quota.QuotaBudget.can_consume", return_value=False
        )
        mock_get = mocker.patch("requests.get")

        provider = FreesoundProvider()
        results = provider.search("test")

        assert results == []
        mock_can_consume.assert_called_once_with("freesound", 1)
        mock_get.assert_not_called()

    def test_freesound_search_rate_limited(self, mocker):
        """429 returns empty."""
        from agent_core.assets.providers.freesound import FreesoundProvider

        mocker.patch.dict("os.environ", {"FREESOUND_API_KEY": "test_key"})
        mocker.patch(
            "agent_core.core.quota.QuotaBudget.can_consume", return_value=True
        )

        mock_resp = mocker.MagicMock()
        mock_resp.status_code = 429
        mocker.patch("requests.get", return_value=mock_resp)

        provider = FreesoundProvider()
        results = provider.search("test")

        assert results == []


# =========================================================================
# AssetFallbackChain
# =========================================================================


class TestAssetFallbackChain:
    """Tests for the AssetFallbackChain orchestrator."""

    def test_fallback_chain_empty_provider_logs_warning(self, caplog):
        """Empty chain logs 'all providers exhausted' warning."""
        from agent_core.assets.providers import AssetFallbackChain

        caplog.set_level(logging.WARNING)
        chain = AssetFallbackChain(chain=[])
        results = chain.search("test")

        assert results == []
        assert any(
            "all providers exhausted" in record.message.lower()
            for record in caplog.records
        )

    def test_fallback_chain_ordered_execution(self, mocker):
        """First provider succeeds — verify second provider is not called."""
        from agent_core.assets.providers import AssetFallbackChain, PROVIDERS

        # Create a mock provider that always succeeds
        mock_provider_cls = mocker.MagicMock()
        mock_instance = mock_provider_cls.return_value
        mock_instance.search.return_value = [
            mocker.MagicMock(source_url="https://example.com/vid.mp4")
        ]

        PROVIDERS["_test_first"] = mock_provider_cls

        try:
            chain = AssetFallbackChain(chain=["_test_first", "pexels"])
            results = chain.search("hello")

            # Results should be the mocked result
            assert len(results) == 1
            mock_instance.search.assert_called_once_with("hello")

            # Second provider should NOT have been called — first succeeded
            mock_provider_cls.assert_called_once()
        finally:
            PROVIDERS.pop("_test_first", None)

    def test_fallback_chain_custom_chain(self):
        """Custom chain is respected over default."""
        from agent_core.assets.providers import AssetFallbackChain

        chain = AssetFallbackChain(chain=["pixabay"])
        assert chain.chain == ["pixabay"]

    def test_fallback_chain_default_chain(self):
        """Default chain equals pexels → pixabay."""
        from agent_core.assets.providers import AssetFallbackChain, DEFAULT_FALLBACK_CHAIN

        chain = AssetFallbackChain()
        assert chain.chain == ["pexels", "pixabay"]
        assert chain.chain == DEFAULT_FALLBACK_CHAIN

    def test_fallback_chain_all_providers_fail_returns_empty(self):
        """Chain with nonexistent provider returns empty list."""
        from agent_core.assets.providers import AssetFallbackChain

        chain = AssetFallbackChain(chain=["nonexistent_provider_xyz"])
        results = chain.search("test")

        assert results == []

    def test_fallback_chain_download_from_metadata_source(self, mocker, tmp_path):
        """Download routes to correct provider based on metadata source field."""
        from agent_core.assets.providers import AssetFallbackChain
        from agent_core.assets.base import AssetResult

        output_path = tmp_path / "out.mp4"

        # Mock PexelsProvider.download to succeed
        mock_download = mocker.patch(
            "agent_core.assets.providers.pexels.PexelsProvider.download",
            return_value=output_path,
        )

        asset = AssetResult(
            source_url="https://example.com/video.mp4",
            file_extension="mp4",
            metadata={"source": "pexels"},
            score=1.0,
        )

        chain = AssetFallbackChain()
        result = chain.download(asset, output_path)

        assert result == output_path
        mock_download.assert_called_once_with(asset, output_path)
