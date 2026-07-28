"""
Tests for the Wikimedia Commons asset provider.

Covers search (with and without British Library boost), download,
error handling, rate limiting, quota exhaustion, and the fallback
chain integration.
"""

from pathlib import Path

import pytest
import requests


# Helper: create a provider that bypasses quota for search tests
def _make_provider():
    """Create a WikimediaCommonsProvider with quota checks bypassed.

    The persisted quota file doesn't have ``wikimedia_commons`` yet,
    so we mock ``can_consume`` and ``consume`` for search tests.
    """
    from agent_core.assets.providers.wikimedia import WikimediaCommonsProvider
    provider = WikimediaCommonsProvider()
    provider.quota.can_consume = lambda *a, **kw: True
    provider.quota.consume = lambda *a, **kw: True
    return provider


class TestWikimediaCommonsProvider:
    """Tests for WikimediaCommonsProvider — search, download, and errors."""

    def test_init_no_key_needed(self):
        """Provider initialises without any API key."""
        from agent_core.assets.providers.wikimedia import WikimediaCommonsProvider
        provider = WikimediaCommonsProvider()
        assert provider.api_key is None

    def test_search_with_british_library_boost(self, mocker, mock_wikimedia_response):
        """With british_library_boost=True, searches 'query British Library' first."""
        provider = _make_provider()

        mock_get = mocker.patch("requests.get")
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = mock_wikimedia_response

        results = provider.search("vintage illustration", per_page=5)

        assert len(results) == 1
        assert results[0].metadata["source"] == "wikimedia_commons"
        assert results[0].score == 0.95
        assert results[0].metadata["british_library"] is True

        call_params = mock_get.call_args[1]["params"]
        assert "british library" in call_params["gsrsearch"].lower()

    def test_search_british_library_empty_falls_back_to_bare(
        self, mocker, mock_wikimedia_response
    ):
        """When BL search returns empty, falls back to bare query."""
        provider = _make_provider()

        mock_get = mocker.patch("requests.get")
        empty_response = {"batchcomplete": "", "query": {"pages": {}}}
        mock_get.side_effect = [
            mocker.Mock(status_code=200, json=lambda: empty_response),
            mocker.Mock(status_code=200, json=lambda: mock_wikimedia_response),
        ]

        results = provider.search("vintage illustration", per_page=5)

        assert len(results) == 1
        assert results[0].score == 0.85
        assert mock_get.call_count == 2

    def test_search_disabled_british_library_boost(self, mocker, mock_wikimedia_response):
        """With british_library_boost=False, searches bare query only."""
        provider = _make_provider()

        mock_get = mocker.patch("requests.get")
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = mock_wikimedia_response

        results = provider.search("vintage", per_page=5, british_library_boost=False)

        assert len(results) == 1
        assert results[0].score == 0.85
        call_params = mock_get.call_args[1]["params"]
        assert "british" not in call_params["gsrsearch"].lower()

    def test_search_mocked_response_metadata(self, mocker, mock_wikimedia_response):
        """Verify all metadata fields are correctly extracted."""
        provider = _make_provider()

        mock_get = mocker.patch("requests.get")
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = mock_wikimedia_response

        results = provider.search("test", british_library_boost=True)
        assert len(results) == 1
        meta = results[0].metadata
        assert meta["page_id"] == 12345
        assert meta["title"] == "File:Vintage_illustration_example.jpg"
        assert meta["license"] == "Public domain"
        assert meta["width"] == 1800
        assert meta["height"] == 1200
        assert results[0].file_extension == "jpg"

    def test_search_artist_html_stripped(self, mocker):
        """Artist HTML tags are stripped from extmetadata."""
        provider = _make_provider()

        response = {
            "batchcomplete": "",
            "query": {
                "pages": {
                    "1": {
                        "pageid": 1,
                        "ns": 6,
                        "title": "File:Test.jpg",
                        "imageinfo": [
                            {
                                "url": "https://upload.wikimedia.org/wikipedia/commons/test.jpg",
                                "descriptionurl": "https://commons.wikimedia.org/wiki/File:Test.jpg",
                                "extmetadata": {
                                    "Artist": {
                                        "value": '<a href="https://example.com">John Doe</a>',
                                        "source": "commons",
                                    },
                                    "LicenseShortName": {
                                        "value": "CC BY-SA 4.0",
                                        "source": "commons",
                                    },
                                },
                            }
                        ],
                    }
                }
            },
        }

        mock_get = mocker.patch("requests.get")
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = response

        results = provider.search("test", british_library_boost=True)
        assert len(results) == 1
        assert results[0].metadata["artist"] == "John Doe"

    def test_search_rate_limited_returns_empty(self, mocker):
        """429 responses return empty list."""
        provider = _make_provider()

        mock_get = mocker.patch("requests.get")
        mock_get.return_value.status_code = 429

        results = provider.search("test")
        assert results == []

    def test_search_network_error_returns_empty(self, mocker):
        """Connection errors return empty list."""
        provider = _make_provider()

        mocker.patch(
            "requests.get",
            side_effect=requests.ConnectionError("network error"),
        )

        results = provider.search("test")
        assert results == []

    def test_search_quota_exhausted_returns_empty(self, mocker):
        """When QuotaBudget is exhausted, returns empty without API call."""
        from agent_core.assets.providers.wikimedia import WikimediaCommonsProvider
        provider = WikimediaCommonsProvider()

        mocker.patch.object(provider.quota, "can_consume", return_value=False)
        mock_get = mocker.patch("requests.get")

        results = provider.search("test")
        assert results == []
        mock_get.assert_not_called()

    def test_download_success(self, mocker, tmp_path):
        """Successful download writes file and returns path."""
        from agent_core.assets.base import AssetResult
        provider = _make_provider()

        asset = AssetResult(
            source_url="https://upload.wikimedia.org/wikipedia/commons/test.jpg",
            file_extension="jpg",
            metadata={"source": "wikimedia_commons"},
        )

        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.iter_content.return_value = [b"test_image_data"]
        mocker.patch("requests.get", return_value=mock_response)

        output_path = tmp_path / "downloads" / "test.jpg"
        result = provider.download(asset, output_path)

        assert result == output_path
        assert output_path.read_bytes() == b"test_image_data"

    def test_download_failure_returns_none(self, mocker):
        """Download failure returns None, never raises."""
        from agent_core.assets.base import AssetResult
        provider = _make_provider()

        asset = AssetResult(
            source_url="https://upload.wikimedia.org/wikipedia/commons/test.jpg",
            file_extension="jpg",
            metadata={"source": "wikimedia_commons"},
        )

        mocker.patch(
            "requests.get",
            side_effect=requests.ConnectionError("timeout"),
        )

        result = provider.download(asset, Path("/tmp/nonexistent/test.jpg"))
        assert result is None

    def test_empty_response_handling(self, mocker):
        """API returning empty pages dict produces empty result list."""
        provider = _make_provider()

        empty_response = {"batchcomplete": "", "query": {"pages": {}}}
        mock_get = mocker.patch("requests.get")
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = empty_response

        results = provider.search("vintage", british_library_boost=True)
        assert results == []


class TestWikimediaExtensionDetection:
    """Tests for the static _detect_extension method."""

    def _detect(self, url, title=""):
        from agent_core.assets.providers.wikimedia import WikimediaCommonsProvider
        return WikimediaCommonsProvider._detect_extension(url, title)

    def test_jpg_from_url(self):
        assert self._detect("https://example.com/image.jpg") == "jpg"

    def test_jpeg_from_url(self):
        assert self._detect("https://example.com/image.jpeg") == "jpg"

    def test_png_from_url(self):
        assert self._detect("https://example.com/image.png") == "png"

    def test_svg_from_url(self):
        assert self._detect("https://example.com/image.svg") == "svg"

    def test_gif_from_url(self):
        assert self._detect("https://example.com/animated.gif") == "gif"

    def test_webp_from_url(self):
        assert self._detect("https://example.com/image.webp") == "webp"

    def test_tiff_from_url(self):
        assert self._detect("https://example.com/image.tiff") == "tiff"

    def test_unknown_extension_falls_back_to_jpg(self):
        assert self._detect("https://example.com/image.bmp") == "jpg"

    def test_no_extension_falls_back_to_jpg(self):
        assert self._detect("https://example.com/image") == "jpg"

    def test_title_fallback_for_extension(self):
        """Uses title when URL has no recognizable extension."""
        url = "https://upload.wikimedia.org/wikipedia/commons/abc/File_Name"
        title = "File:Example diagram.svg"
        assert self._detect(url, title) == "svg"


class TestProviderRegistration:
    """Tests that WikimediaCommonsProvider is registered correctly."""

    def test_registered_in_PROVIDERS(self):
        """Provider appears in the PROVIDERS registry."""
        from agent_core.assets.providers import PROVIDERS
        assert "wikimedia_commons" in PROVIDERS

    def test_not_in_default_fallback_chain(self):
        """Wikimedia Commons is NOT in DEFAULT_FALLBACK_CHAIN (images only)."""
        from agent_core.assets.providers import DEFAULT_FALLBACK_CHAIN
        assert "wikimedia_commons" not in DEFAULT_FALLBACK_CHAIN

    def test_importable_from_barrel(self):
        """Provider is importable from the top-level assets module."""
        from agent_core.assets import WikimediaCommonsProvider
        assert WikimediaCommonsProvider is not None

    def test_provider_instantiable_from_registry(self):
        """Provider can be instantiated via the PROVIDERS dict."""
        from agent_core.assets.providers import PROVIDERS
        provider_cls = PROVIDERS["wikimedia_commons"]
        provider = provider_cls()
        assert provider is not None


class TestAssetFallbackChainWithWikimedia:
    """Tests for fallback chain behavior when Wikimedia is in the chain."""

    def test_wikimedia_not_in_default_chain(self):
        """Default chain remains pexels → pixabay."""
        from agent_core.assets.providers import AssetFallbackChain
        chain = AssetFallbackChain()
        assert chain.chain == ["pexels", "pixabay"]

    def test_custom_chain_with_wikimedia(self, mocker):
        """Custom chain including wikimedia_commons works correctly."""
        from agent_core.assets.providers import AssetFallbackChain
        from agent_core.assets.providers.wikimedia import WikimediaCommonsProvider

        mock_wm_result = mocker.Mock(
            source_url="https://commons.wikimedia.org/test.jpg",
            metadata={"source": "wikimedia_commons"},
        )

        mocker.patch.object(
            WikimediaCommonsProvider, "search", return_value=[mock_wm_result]
        )

        chain = AssetFallbackChain(chain=["wikimedia_commons"])
        results = chain.search("vintage illustration")
        assert len(results) == 1
        assert results[0].metadata["source"] == "wikimedia_commons"
