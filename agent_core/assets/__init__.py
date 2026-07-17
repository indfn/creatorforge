"""Visual Asset Pipeline — base abstractions, storage, cache, and search."""
from agent_core.assets.base import BaseAssetProvider, AssetResult
from agent_core.assets.storage import (
    consistent_asset_path, temp_asset_dir, compute_content_hash, build_asset_filename,
)
from agent_core.assets.cache import AssetCache
from agent_core.assets.search import generate_search_query, generate_sfx_query

__all__ = [
    "BaseAssetProvider", "AssetResult",
    "consistent_asset_path", "temp_asset_dir", "compute_content_hash", "build_asset_filename",
    "AssetCache",
    "generate_search_query", "generate_sfx_query",
]
