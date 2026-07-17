"""Visual Asset Pipeline — stock API sourcing, cache layer, storage, and character SVG resolution.

Top-level imports::

    from agent_core.assets import (
        # Base
        BaseAssetProvider, AssetResult,
        # Providers
        PexelsProvider, PixabayProvider, FreesoundProvider,
        AssetFallbackChain, PROVIDERS, DEFAULT_FALLBACK_CHAIN,
        # Cache
        AssetCache,
        # Storage
        consistent_asset_path, temp_asset_dir,
        compute_content_hash, build_asset_filename,
        # Characters
        CharacterResolver,
        # Search
        generate_search_query, generate_sfx_query,
        # Lifecycle
        TempAssetManifest, register_temp_cleanup,
    )
"""

# Base
from agent_core.assets.base import BaseAssetProvider, AssetResult

# Providers
from agent_core.assets.providers import (
    PexelsProvider,
    PixabayProvider,
    FreesoundProvider,
    AssetFallbackChain,
    PROVIDERS,
    DEFAULT_FALLBACK_CHAIN,
)

# Cache
from agent_core.assets.cache import AssetCache

# Storage
from agent_core.assets.storage import (
    consistent_asset_path,
    temp_asset_dir,
    compute_content_hash,
    build_asset_filename,
    asset_metadata_sidecar_path,
)

# Search
from agent_core.assets.search import generate_search_query, generate_sfx_query

# Characters
from agent_core.assets.characters import CharacterResolver

# Temp asset lifecycle (re-exports from audio/lifecycle.py for convenience)
from agent_core.audio.lifecycle import TempAssetManifest, register_temp_cleanup

__all__ = [
    # Base
    "BaseAssetProvider",
    "AssetResult",
    # Providers
    "PexelsProvider",
    "PixabayProvider",
    "FreesoundProvider",
    "AssetFallbackChain",
    "PROVIDERS",
    "DEFAULT_FALLBACK_CHAIN",
    # Cache
    "AssetCache",
    # Storage
    "consistent_asset_path",
    "temp_asset_dir",
    "compute_content_hash",
    "build_asset_filename",
    "asset_metadata_sidecar_path",
    # Search
    "generate_search_query",
    "generate_sfx_query",
    # Characters
    "CharacterResolver",
    # Lifecycle
    "TempAssetManifest",
    "register_temp_cleanup",
]
