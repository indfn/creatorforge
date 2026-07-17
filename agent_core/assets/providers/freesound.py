"""
Freesound API provider for SFX (sound effects).

Uses the Freesound API (``/apiv2/search/`` endpoint) with token auth via query param.
CRITICAL: Download uses ``previews.preview-hq-mp3`` URLs — NOT the ``/download/``
endpoint (which requires OAuth2). Preview URLs are CDN-hosted and work without auth.
Rate limit: 60 requests/min, 2,000 requests/day.

See:
    https://freesound.org/docs/api/resources_apiv2.html
"""

import logging
import os
from pathlib import Path
from typing import Optional

import requests

from agent_core.assets.base import BaseAssetProvider, AssetResult
from agent_core.core.quota import QuotaBudget

logger = logging.getLogger(__name__)

FREESOUND_API_URL = "https://freesound.org/apiv2"


class FreesoundProvider(BaseAssetProvider):
    """Freesound API provider for SFX.

    Requires ``FREESOUND_API_KEY`` environment variable.
    Quota is tracked via ``QuotaBudget`` under the ``"freesound"`` budget name.

    IMPORTANT:
        Download uses preview URLs from search results, NOT the ``/download/``
        endpoint. The ``/download/`` endpoint requires OAuth2 authentication.
        Preview URLs (``preview-hq-mp3``, ``preview-lq-mp3``) are CDN-hosted
        and work without any authentication.
    """

    def __init__(self):
        """Initialise the provider — loads API key and quota tracker."""
        self.api_key = os.environ.get("FREESOUND_API_KEY", "")
        if not self.api_key:
            logger.warning("FREESOUND_API_KEY not set — Freesound provider disabled")
        self.quota = QuotaBudget()

    def search(
        self,
        query: str,
        duration_max: int = 15,
        page_size: int = 10,
        **kwargs,
    ) -> list[AssetResult]:
        """Search Freesound for SFX.

        Filters results to short sounds (0.1 to ``duration_max`` seconds) suitable
        for sound effects. Uses the ``fields`` parameter to limit response size.

        Args:
            query: Search keywords.
            duration_max: Maximum duration in seconds for results (default 15).
            page_size: Number of results per page (max 150).
            **kwargs: Passed through to API (unused).

        Returns:
            List of ``AssetResult`` with ``file_extension="mp3"``, or empty list
            on failure.
        """
        if not self.api_key:
            return []

        if not self.quota.can_consume("freesound", 1):
            logger.warning("Freesound quota exhausted — skipping search")
            return []

        # Filter for short sounds suitable as SFX
        filter_str = f"duration:[0.1 TO {duration_max}]"

        params = {
            "token": self.api_key,
            "query": query,
            "filter": filter_str,
            "page_size": min(page_size, 150),
            "fields": "id,name,tags,duration,previews,license,username",
            "sort": "score",
        }

        try:
            resp = requests.get(
                f"{FREESOUND_API_URL}/search/",
                params=params,
                timeout=15,
            )
            self.quota.consume("freesound", 1)

            if resp.status_code == 429:
                logger.warning("Freesound rate limit hit (429)")
                return []

            resp.raise_for_status()
            data = resp.json()

            results: list[AssetResult] = []
            for sound in data.get("results", []):
                previews = sound.get("previews", {})
                # Prefer HQ mp3, fallback to LQ mp3
                audio_url = previews.get("preview-hq-mp3") or previews.get("preview-lq-mp3")
                if not audio_url:
                    continue

                results.append(
                    AssetResult(
                        source_url=audio_url,
                        file_extension="mp3",
                        metadata={
                            "source": "freesound",
                            "sound_id": sound["id"],
                            "name": sound.get("name", ""),
                            "tags": sound.get("tags", []),
                            "duration": sound.get("duration"),
                            "license": sound.get("license", ""),
                            "username": sound.get("username", ""),
                        },
                        score=1.0,
                    )
                )

            return results

        except requests.RequestException as e:
            logger.warning("Freesound API error: %s", e)
            return []

    def download(self, asset: AssetResult, output_path: Path) -> Optional[Path]:
        """Download an asset file to disk.

        CRITICAL: The ``source_url`` is a CDN preview URL (not a download endpoint).
        No auth headers are needed for preview URLs.

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
