"""
Pexels API provider for B-roll footage and images.

Uses the Pexels API (``/v1/videos/search`` endpoint) with Authorization header.
Rate limit: 200 requests/hr, 20,000/month.

See:
    https://www.pexels.com/api/documentation/
"""

import logging
import os
from pathlib import Path
from typing import Optional

import requests

from agent_core.assets.base import BaseAssetProvider, AssetResult
from agent_core.core.quota import QuotaBudget

logger = logging.getLogger(__name__)

PEXELS_API_URL = "https://api.pexels.com/v1"


class PexelsProvider(BaseAssetProvider):
    """Pexels API provider for B-roll footage and images.

    Requires ``PEXELS_API_KEY`` environment variable.
    Quota is tracked via ``QuotaBudget`` under the ``"pexels"`` budget name.
    """

    def __init__(self):
        """Initialise the provider — loads API key and quota tracker."""
        self.api_key = os.environ.get("PEXELS_API_KEY", "")
        if not self.api_key:
            logger.warning("PEXELS_API_KEY not set — Pexels provider disabled")
        self.quota = QuotaBudget()

    def search(
        self,
        query: str,
        per_page: int = 5,
        orientation: str = "portrait",
        **kwargs,
    ) -> list[AssetResult]:
        """Search Pexels for videos.

        Args:
            query: Search keywords.
            per_page: Number of results (max 80).
            orientation: Video orientation filter ("portrait", "landscape", "square").
            **kwargs: Passed through to API (unused).

        Returns:
            List of ``AssetResult`` ordered by relevance, or empty list on failure.
        """
        if not self.api_key:
            return []

        if not self.quota.can_consume("pexels", 1):
            logger.warning("Pexels quota exhausted — skipping search")
            return []

        headers = {"Authorization": self.api_key}
        params = {
            "query": query,
            "per_page": min(per_page, 80),
            "orientation": orientation,
        }

        try:
            resp = requests.get(
                f"{PEXELS_API_URL}/videos/search",
                headers=headers,
                params=params,
                timeout=15,
            )
            self.quota.consume("pexels", 1)

            if resp.status_code == 429:
                logger.warning("Pexels rate limit hit (429)")
                return []

            resp.raise_for_status()
            data = resp.json()

            results: list[AssetResult] = []
            for video in data.get("videos", []):
                video_files = video.get("video_files", [])
                best = next(
                    (f for f in video_files if f.get("quality") == "hd"),
                    video_files[0] if video_files else None,
                )
                if not best:
                    continue

                results.append(
                    AssetResult(
                        source_url=best["link"],
                        file_extension="mp4",
                        metadata={
                            "source": "pexels",
                            "video_id": video["id"],
                            "photographer": video.get("user", {}).get("name", ""),
                            "duration": video.get("duration"),
                            "width": best.get("width"),
                            "height": best.get("height"),
                            "license": "Pexels License (free use with attribution)",
                        },
                        score=1.0,
                    )
                )

            return results

        except requests.RequestException as e:
            logger.warning("Pexels API error: %s", e)
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
