"""
Pixabay API provider — fallback for B-roll footage and images.

Uses the Pixabay API (``/api/videos/`` endpoint) with API key as query param.
Acts as fallback when Pexels is unavailable or returns no results.
Rate limit: 100 requests per 60 seconds. ``totalHits`` capped at 500 per query.

See:
    https://pixabay.com/api/docs/
"""

import logging
import os
from pathlib import Path
from typing import Optional

import requests

from agent_core.assets.base import BaseAssetProvider, AssetResult
from agent_core.core.quota import QuotaBudget

logger = logging.getLogger(__name__)

PIXABAY_API_URL = "https://pixabay.com/api"


class PixabayProvider(BaseAssetProvider):
    """Pixabay API provider — fallback for images/video when Pexels fails.

    Requires ``PIXABAY_API_KEY`` environment variable.
    Quota is tracked via ``QuotaBudget`` under the ``"pixabay"`` budget name.
    """

    def __init__(self):
        """Initialise the provider — loads API key and quota tracker."""
        self.api_key = os.environ.get("PIXABAY_API_KEY", "")
        if not self.api_key:
            logger.warning("PIXABAY_API_KEY not set — Pixabay provider disabled")
        self.quota = QuotaBudget()

    def search(
        self,
        query: str,
        per_page: int = 5,
        **kwargs,
    ) -> list[AssetResult]:
        """Search Pixabay for videos.

        Args:
            query: Search keywords.
            per_page: Number of results (Pixabay requires 3-200 range; clamped).
            **kwargs: Passed through to API (unused).

        Returns:
            List of ``AssetResult`` with score=0.9 (fallback priority), or empty
            list on failure.
        """
        if not self.api_key:
            return []

        if not self.quota.can_consume("pixabay", 1):
            logger.warning("Pixabay quota exhausted — skipping search")
            return []

        params = {
            "key": self.api_key,
            "q": query,
            "per_page": min(max(per_page, 3), 200),  # Pixabay range: 3-200
        }

        try:
            resp = requests.get(
                f"{PIXABAY_API_URL}/videos/",
                params=params,
                timeout=15,
            )

            if resp.status_code == 429:
                logger.warning("Pixabay rate limit hit (429)")
                return []

            self.quota.consume("pixabay", 1)

            resp.raise_for_status()
            data = resp.json()

            results: list[AssetResult] = []
            for hit in data.get("hits", []):
                videos = hit.get("videos", {})
                # Prefer medium (1080p), fallback to small (720p), then tiny
                selected = videos.get("medium") or videos.get("small") or videos.get("tiny")
                if not selected:
                    continue

                results.append(
                    AssetResult(
                        source_url=selected["url"],
                        file_extension="mp4",
                        metadata={
                            "source": "pixabay",
                            "video_id": hit["id"],
                            "tags": hit.get("tags", ""),
                            "duration": hit.get("duration"),
                            "width": selected.get("width"),
                            "height": selected.get("height"),
                            "license": "Pixabay Content License (free use)",
                        },
                        score=0.9,  # Slightly lower priority than Pexels
                    )
                )

            return results

        except requests.RequestException as e:
            logger.warning("Pixabay API error: %s", e)
            return []

    def download(self, asset: AssetResult, output_path: Path) -> Optional[Path]:
        """Download an asset file to disk.

        Args:
            asset: The asset to download (uses ``source_url``).
            output_path: Destination path on disk.

        Returns:
            ``output_path`` on success, ``None`` on failure.
        """
        try:
            resp = requests.get(asset.source_url, stream=True, timeout=30)
            resp.raise_for_status()

            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            return output_path

        except requests.RequestException as e:
            logger.warning("Download failed: %s — %s", asset.source_url, e)
            return None
