"""
Base asset provider abstraction — defines the AssetResult dataclass and BaseAssetProvider contract.

All asset providers inherit from BaseAssetProvider and implement the ``search()``
and ``download()`` methods.
"""

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class AssetResult:
    """Result of an asset search.

    Attributes:
        source_url: Direct URL to download the asset.
        file_extension: File extension (mp4, jpg, wav, etc.).
        metadata: Dict with source, license, photographer, tags, etc.
        score: Relevance score for ranking results (0.0 - 1.0).
    """
    source_url: str
    file_extension: str
    metadata: dict
    score: float = 0.0


class BaseAssetProvider(ABC):
    """Abstract base class for all visual/SFX asset providers.

    Subclasses must implement ``search()`` and ``download()``.
    """

    @abstractmethod
    def search(self, query: str, **kwargs) -> list[AssetResult]:
        """Search for assets matching the query.

        Args:
            query: Search keywords.
            **kwargs: Provider-specific filters (orientation, size, duration, etc.).

        Returns:
            List of AssetResult, ordered by relevance. Empty list on failure — never raises.
        """
        ...

    @abstractmethod
    def download(self, asset: AssetResult, output_path: Path) -> Optional[Path]:
        """Download an asset to the given path.

        Returns:
            Path to the downloaded file, or None on failure.
        """
        ...

    def search_and_download(
        self, query: str, output_path: Path, **kwargs
    ) -> Optional[Path]:
        """Convenience: search then download the best result.

        Searches for assets matching the query, picks the highest-score result,
        and downloads it. Returns None if search returns empty or download fails.
        Never raises.
        """
        try:
            results = self.search(query, **kwargs)
            if not results:
                return None
            best = max(results, key=lambda r: r.score)
            return self.download(best, output_path)
        except Exception as e:
            logger.warning("search_and_download failed: %s", e)
            return None
