"""
Tests for BaseAssetProvider ABC and AssetResult dataclass.

Covers:
    - ABC instantiation guard (cannot instantiate directly)
    - AssetResult field defaults and types
    - Concrete subclass can implement search() and download()
"""

from pathlib import Path

import pytest


class TestAssetResult:
    """Tests for the AssetResult dataclass."""

    def test_asset_result_dataclass_fields(self):
        """Verify AssetResult has all 4 expected fields with correct types."""
        from agent_core.assets.base import AssetResult

        result = AssetResult(
            source_url="https://example.com/video.mp4",
            file_extension="mp4",
            metadata={"source": "pexels", "photographer": "Test"},
            score=0.85,
        )

        assert result.source_url == "https://example.com/video.mp4"
        assert result.file_extension == "mp4"
        assert result.metadata == {"source": "pexels", "photographer": "Test"}
        assert result.score == 0.85

    def test_asset_result_score_defaults_to_zero(self):
        """Verify score defaults to 0.0 when not provided."""
        from agent_core.assets.base import AssetResult

        result = AssetResult(
            source_url="https://example.com/video.mp4",
            file_extension="mp4",
            metadata={},
        )

        assert result.score == 0.0

    def test_asset_result_types(self):
        """Verify type hints are enforced by dataclass (string coerce not automatic)."""
        from agent_core.assets.base import AssetResult

        result = AssetResult(
            source_url="https://example.com/v.mp4",
            file_extension="mp4",
            metadata={"key": "value"},
            score=1.0,
        )
        assert isinstance(result.source_url, str)
        assert isinstance(result.file_extension, str)
        assert isinstance(result.metadata, dict)
        assert isinstance(result.score, float)


class TestBaseAssetProvider:
    """Tests for the abstract base provider class."""

    def test_base_class_cannot_be_instantiated(self):
        """ABC should raise TypeError when instantiated directly."""
        from agent_core.assets.base import BaseAssetProvider

        with pytest.raises(TypeError):
            BaseAssetProvider()  # type: ignore[abstract]

    def test_concrete_provider_can_be_instantiated(self):
        """A minimal subclass implementing search and download should work."""
        from agent_core.assets.base import BaseAssetProvider, AssetResult

        class MinimalProvider(BaseAssetProvider):
            def search(self, query: str, **kwargs) -> list[AssetResult]:
                return [
                    AssetResult(
                        source_url="https://example.com/v.mp4",
                        file_extension="mp4",
                        metadata={"source": "test"},
                        score=1.0,
                    )
                ]

            def download(self, asset: AssetResult, output_path: Path):
                return output_path

        provider = MinimalProvider()
        results = provider.search("test query")
        assert len(results) == 1
        assert results[0].source_url == "https://example.com/v.mp4"

    def test_search_and_download_convenience_happy_path(self):
        """search_and_download returns path when search succeeds and download works."""
        from agent_core.assets.base import BaseAssetProvider, AssetResult
        from pathlib import Path

        class ReturningProvider(BaseAssetProvider):
            def search(self, query: str, **kwargs) -> list[AssetResult]:
                return [
                    AssetResult("https://example.com/best.mp4", "mp4", {}, 0.9),
                    AssetResult("https://example.com/worse.mp4", "mp4", {}, 0.5),
                ]

            def download(self, asset: AssetResult, output_path: Path):
                return output_path

        provider = ReturningProvider()
        result = provider.search_and_download("test", Path("/tmp/out.mp4"))
        assert result == Path("/tmp/out.mp4")

    def test_search_and_download_empty_results_returns_none(self):
        """search_and_download returns None when search returns empty."""
        from agent_core.assets.base import BaseAssetProvider, AssetResult
        from pathlib import Path

        class EmptyProvider(BaseAssetProvider):
            def search(self, query: str, **kwargs) -> list[AssetResult]:
                return []

            def download(self, asset: AssetResult, output_path: Path):
                return output_path

        provider = EmptyProvider()
        result = provider.search_and_download("test", Path("/tmp/out.mp4"))
        assert result is None

    def test_search_and_download_never_raises_on_error(self):
        """search_and_download catches exceptions and returns None."""
        from agent_core.assets.base import BaseAssetProvider, AssetResult
        from pathlib import Path

        class FailingProvider(BaseAssetProvider):
            def search(self, query: str, **kwargs) -> list[AssetResult]:
                raise RuntimeError("API failure")

            def download(self, asset: AssetResult, output_path: Path):
                raise RuntimeError("should not be called")

        provider = FailingProvider()
        # Should not raise — returns None instead
        result = provider.search_and_download("test", Path("/tmp/out.mp4"))
        assert result is None
