"""Provider registry and fallback chain — tries asset providers in order until one succeeds.

Providers are registered in the ``PROVIDERS`` dict at module level.
"""

import logging
from pathlib import Path
from typing import Optional

from agent_core.assets.base import BaseAssetProvider, AssetResult
from agent_core.assets.providers.pexels import PexelsProvider
from agent_core.assets.providers.pixabay import PixabayProvider
from agent_core.assets.providers.freesound import FreesoundProvider

logger = logging.getLogger(__name__)

# Registry of all available asset providers.
PROVIDERS: dict[str, type[BaseAssetProvider]] = {
    "pexels": PexelsProvider,
    "pixabay": PixabayProvider,
    "freesound": FreesoundProvider,
}

# Default fallback order for B-roll/images — Pexels primary, Pixabay fallback.
DEFAULT_FALLBACK_CHAIN = ["pexels", "pixabay"]

__all__ = [
    "PexelsProvider",
    "PixabayProvider",
    "FreesoundProvider",
    "AssetFallbackChain",
    "PROVIDERS",
    "DEFAULT_FALLBACK_CHAIN",
]


class AssetFallbackChain:
    """Orchestrates asset provider fallback.

    Tries each provider in ``chain`` order. Returns the first successful result
    or empty list if all providers fail (never raises).
    """

    def __init__(
        self,
        chain: Optional[list[str]] = None,
        provider_configs: Optional[dict] = None,
    ):
        """Initialise the fallback chain.

        Args:
            chain: Ordered list of provider names to try. Defaults to
                ``DEFAULT_FALLBACK_CHAIN`` (pexels → pixabay).
            provider_configs: Per-provider init kwargs dict, keyed by provider name.
        """
        self.chain = list(chain) if chain else list(DEFAULT_FALLBACK_CHAIN)
        self.provider_configs = provider_configs or {}

    def search(self, query: str, **kwargs) -> list[AssetResult]:
        """Search across the provider chain.

        Tries each provider in order. Returns the first non-empty result list
        or an empty list if all providers fail (never raises).

        Args:
            query: Search keywords.
            **kwargs: Passed to each provider's ``search()`` method.

        Returns:
            List of ``AssetResult`` from the first successful provider, or empty
            list if all providers in the chain failed.
        """
        for provider_name in self.chain:
            provider_cls = PROVIDERS.get(provider_name)
            if provider_cls is None:
                logger.warning(
                    "AssetFallbackChain: unknown provider %r — skipping", provider_name
                )
                continue

            try:
                kwargs_init = self.provider_configs.get(provider_name, {})
                provider = provider_cls(**kwargs_init)

                results = provider.search(query, **kwargs)
                if results:
                    logger.info(
                        "AssetFallbackChain: %s returned %d results",
                        provider_name,
                        len(results),
                    )
                    return results

                logger.warning(
                    "AssetFallbackChain: %s returned empty — trying next",
                    provider_name,
                )
            except Exception as e:
                logger.warning(
                    "AssetFallbackChain: %s raised %s — trying next",
                    provider_name,
                    e,
                )

        logger.error("AssetFallbackChain: all providers exhausted — no assets found")
        return []

    def download(self, asset: AssetResult, output_path: Path) -> Optional[Path]:
        """Download an asset using the fallback chain.

        Since we already know which provider returned the result, instantiate
        the correct provider type from the asset's metadata ``source`` field.

        Args:
            asset: The asset to download (``asset.metadata["source"]`` identifies
                the provider).
            output_path: Destination path on disk.

        Returns:
            ``output_path`` on success, ``None`` on failure.
        """
        source = asset.metadata.get("source", "")
        provider_cls = PROVIDERS.get(source)
        if provider_cls is None:
            logger.warning(
                "AssetFallbackChain: unknown source %r — cannot download", source
            )
            return None
        try:
            provider = provider_cls()
            return provider.download(asset, output_path)
        except Exception as e:
            logger.warning(
                "AssetFallbackChain: download via %s failed: %s", source, e
            )
            return None
