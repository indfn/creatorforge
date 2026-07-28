"""
Wikimedia Commons API provider for public-domain and CC-licensed images.

Uses the MediaWiki Action API (no API key required). All files on Commons
are freely licensed or public domain.

Key features:
    - Free, no API key needed
    - ``british_library_boost`` preference: searches with "British Library"
      first (high-quality vintage illustrations), falls back to bare query
    - License metadata extracted from API response (CC / Public Domain)
    - File extension auto-detected from the upload URL

See:
    https://commons.wikimedia.org/w/api.php
    https://www.mediawiki.org/wiki/API:Search
"""

import logging
import os
import re
from pathlib import Path
from typing import Optional

import requests

from agent_core.assets.base import BaseAssetProvider, AssetResult
from agent_core.core.quota import QuotaBudget

logger = logging.getLogger(__name__)

WIKIMEDIA_API_URL = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "CreatorForge/1.0 (VisualAssetPipeline; mailto:dev@creatorforge.local)"


class WikimediaCommonsProvider(BaseAssetProvider):
    """Wikimedia Commons provider for free-license images.

    No API key required — the Commons API is publicly accessible.
    Quota is tracked via ``QuotaBudget`` under ``"wikimedia_commons"`` to
    ensure respectful usage of the free API.

    The ``british_library_boost`` parameter (on by default) implements an
    agent preference: when the pipeline needs vintage / historical /
    illustrated imagery, British Library uploads are preferred because they
    contain millions of high-quality public-domain 19th-century digitised
    illustrations, engravings, and botanical prints.
    """

    def __init__(self):
        """Initialise the provider — no API key needed."""
        self.api_key = None
        self.quota = QuotaBudget()

    def search(
        self,
        query: str,
        per_page: int = 10,
        british_library_boost: Optional[bool] = None,
        **kwargs,
    ) -> list[AssetResult]:
        """Search Wikimedia Commons for images.

        Two-phase search when ``british_library_boost`` is enabled:
        1. First, search with ``"{query} British Library"``
        2. If that returns zero results, fall back to the bare query

        If ``british_library_boost`` is not passed explicitly, it defaults to
        the ``WIKIMEDIA_COMMONS_BRITISH_LIBRARY_BOOST`` env var; if that is
        unset, it defaults to ``True``.

        Args:
            query: Search keywords.
            per_page: Number of results per phase (max 50).
            british_library_boost: If True (default), prioritise British
                Library uploads. Set to False for a generic Commons search.
            **kwargs: Passed through to API (unused).

        Returns:
            List of ``AssetResult`` ordered by relevance, or empty list on
            failure. Never raises.
        """
        if british_library_boost is None:
            british_library_boost = os.getenv(
                "WIKIMEDIA_COMMONS_BRITISH_LIBRARY_BOOST", "true"
            ).lower() in ("1", "true", "yes")

        if not self.quota.can_consume("wikimedia_commons", 1):
            logger.warning("Wikimedia Commons quota exceeded — skipping search")
            return []

        # Phase 1: British Library boosted search (if enabled)
        if british_library_boost:
            bl_results = self._search_commons(f"{query} British Library", per_page)
            if bl_results:
                for r in bl_results:
                    r.score = 0.95
                return bl_results

        # Phase 2: Generic Commons search
        results = self._search_commons(query, per_page)
        for r in results:
            r.score = 0.85
        return results

    def _search_commons(self, query: str, per_page: int) -> list[AssetResult]:
        """Execute a single search against the Commons MediaWiki API.

        Args:
            query: Search keywords for the MediaWiki search.
            per_page: Number of results (clamped to 1-50).

        Returns:
            List of ``AssetResult``, or empty list on failure.
        """
        params = {
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrsearch": query,
            "gsrnamespace": 6,
            "gsrlimit": max(1, min(per_page, 50)),
            "prop": "imageinfo",
            "iiprop": "url|extmetadata|dimensions",
        }

        try:
            resp = requests.get(
                WIKIMEDIA_API_URL,
                params=params,
                timeout=15,
                headers={"User-Agent": USER_AGENT},
            )

            if resp.status_code == 429:
                logger.warning("Wikimedia Commons rate limit hit (429)")
                return []

            self.quota.consume("wikimedia_commons", 1)
            resp.raise_for_status()
            data = resp.json()

            pages = (
                data.get("query", {}).get("pages", {})
                if "query" in data
                else {}
            )

            results: list[AssetResult] = []
            # Sort by pageid for deterministic ordering
            sorted_pages = sorted(pages.values(), key=lambda p: p.get("pageid", 0))
            for page in sorted_pages:
                imageinfo = page.get("imageinfo")
                if not imageinfo:
                    continue
                info = imageinfo[0]
                url = info.get("url", "")
                if not url:
                    continue

                ext = self._detect_extension(url, page.get("title", "")) or "jpg"
                extmeta = info.get("extmetadata", {})

                results.append(
                    AssetResult(
                        source_url=url,
                        file_extension=ext,
                        metadata={
                            "source": "wikimedia_commons",
                            "page_id": page.get("pageid"),
                            "title": page.get("title", ""),
                            "artist": self._extract_text(
                                extmeta.get("Artist", {}).get("value", "")
                            ),
                            "license": extmeta.get("LicenseShortName", {}).get(
                                "value", ""
                            ),
                            "credit": extmeta.get("Credit", {}).get("value", ""),
                            "description_url": info.get("descriptionurl", ""),
                            "width": info.get("width"),
                            "height": info.get("height"),
                            "british_library": "british library" in query.lower(),
                        },
                        score=0.85,
                    )
                )

            return results

        except requests.RequestException as e:
            logger.warning("Wikimedia Commons API error: %s", e)
            return []

    def download(self, asset: AssetResult, output_path: Path) -> Optional[Path]:
        """Download an asset file to disk.

        Args:
            asset: The asset to download (uses ``source_url`` — the full
                resolution URL from Commons).
            output_path: Destination path on disk.

        Returns:
            ``output_path`` on success, ``None`` on failure.
        """
        try:
            resp = requests.get(
                asset.source_url,
                stream=True,
                timeout=30,
                headers={"User-Agent": USER_AGENT},
            )
            resp.raise_for_status()

            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            return output_path

        except requests.RequestException as e:
            logger.warning(
                "Wikimedia Commons download failed: %s — %s",
                asset.source_url,
                e,
            )
            return None

    @staticmethod
    def _detect_extension(url: str, title: str = "") -> str:
        """Detect file extension from URL or title.

        Tries the URL path first, then falls back to the page title
        (e.g., ``File:Example.svg`` → ``svg``).

        Args:
            url: The full-resolution URL of the file.
            title: The page title (``File:Filename.ext`` format).

        Returns:
            Lowercase extension without dot, or ``"jpg"`` as fallback.
        """
        # Try the URL path first
        match = re.search(r"\.([a-zA-Z]+)(?:\?|$)", url)
        if match:
            ext = match.group(1).lower()
            if ext in ("jpg", "jpeg", "png", "gif", "svg", "webp", "tiff", "tif"):
                return "jpg" if ext == "jpeg" else ext

        # Fall back to parsing the page title
        if title:
            match = re.search(r"\.([a-zA-Z]+)$", title)
            if match:
                ext = match.group(1).lower()
                if ext in ("jpg", "jpeg", "png", "gif", "svg", "webp", "tiff", "tif"):
                    return "jpg" if ext == "jpeg" else ext

        return "jpg"

    @staticmethod
    def _extract_text(value: str) -> str:
        """Strip HTML tags from extmetadata text values.

        Commons API returns ``Artist`` values with HTML tags like
        ``<a href="...">Name</a>``.

        Args:
            value: Raw HTML string from extmetadata.

        Returns:
            Plain text with HTML tags removed.
        """
        if not value:
            return ""
        return re.sub(r"<[^>]+>", "", value).strip()
