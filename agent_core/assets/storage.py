"""
Asset storage helpers — path resolution for consistent and temp asset directories,
content hashing, filename construction, and metadata sidecar management.

Two-tier storage (D-05):
    - **Consistent assets:** Reusable across videos — global library or per-channel overrides.
    - **Temp assets:** Per-production downloads cleaned after publish.
"""

import hashlib
import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Mapping from asset type key to directory name (D-14).
ASSET_TYPE_DIRS: dict[str, str] = {
    "broll": "broll",
    "image": "images",
    "sfx": "sfx",
    "character": "characters",
}


# =========================================================================
# Private helpers
# =========================================================================


def _project_root() -> Path:
    """Resolve the project root directory (parent of ``agent_core/``)."""
    return Path(__file__).resolve().parent.parent.parent


def _validate_channel(channel: str) -> None:
    """Validate channel name to prevent path traversal (T-10-01).

    Raises:
        ValueError: If channel name contains invalid characters.
    """
    if not re.match(r"^[A-Za-z0-9_-]+$", channel):
        raise ValueError(
            f"Invalid channel name: {channel!r}. "
            "Only letters, numbers, hyphens, underscores allowed."
        )


def _type_dir(asset_type: str, default: str = "misc") -> str:
    """Return the directory name for an asset type, falling back to a default."""
    return ASSET_TYPE_DIRS.get(asset_type, default)


# =========================================================================
# Content hashing (D-15)
# =========================================================================


def compute_content_hash(source_url: str) -> str:
    """Compute an 8-character content hash from a source URL.

    Uses SHA-256 truncated to 8 hex chars for deterministic, collision-resistant
    identification of assets by their source URL (D-15).

    Args:
        source_url: The asset's source URL.

    Returns:
        8-character hex digest.
    """
    return hashlib.sha256(source_url.encode("utf-8")).hexdigest()[:8]


# =========================================================================
# Filename construction (D-13, D-16)
# =========================================================================


def build_asset_filename(
    asset_type: str,
    content_hash: str,
    scene_id: Optional[str] = None,
    extension: str = "mp4",
) -> str:
    """Build a deterministic asset filename following the project convention.

    Format: ``{type}_{hash8}_{scene_id}.{ext}`` when ``scene_id`` is given,
    or ``{type}_{hash8}.{ext}`` when ``scene_id`` is None (D-13, D-16).

    Args:
        asset_type: One of ``"broll"``, ``"image"``, ``"sfx"``, ``"character"``.
        content_hash: 8-character hex content hash (from :func:`compute_content_hash`).
        scene_id: Optional scene identifier for production-scoped assets.
        extension: File extension without leading dot (default ``"mp4"``).

    Returns:
        Formatted filename string.
    """
    if scene_id:
        return f"{asset_type}_{content_hash}_{scene_id}.{extension}"
    return f"{asset_type}_{content_hash}.{extension}"


# =========================================================================
# Consistent path resolution (D-06)
# =========================================================================


def consistent_asset_path(
    asset_type: str,
    filename: str,
    channel: Optional[str] = None,
) -> Path:
    """Resolve the filesystem path for a consistent asset.

    Lookup order (D-05, D-06):
        1. ``channels/{channel}/assets/{type_dir}/{filename}`` — per-channel override.
        2. ``assets/consistent/global/{type_dir}/{filename}`` — global library.

    Args:
        asset_type: One of ``"broll"``, ``"image"``, ``"sfx"``, ``"character"``.
        filename: Asset filename (from :func:`build_asset_filename`).
        channel: Optional channel name for per-channel overrides.

    Returns:
        Absolute ``Path`` to where the asset should be stored or looked up.

    Raises:
        ValueError: If ``channel`` is provided but contains invalid characters.
    """
    root = _project_root()
    type_dir_name = _type_dir(asset_type)

    if channel:
        _validate_channel(channel)
        return root / "channels" / channel / "assets" / type_dir_name / filename

    return root / "assets" / "consistent" / "global" / type_dir_name / filename


# =========================================================================
# Temp path resolution (D-07)
# =========================================================================


def temp_asset_dir(channel: str, production_id: str) -> Path:
    """Resolve the temp asset directory for a production.

    Returns ``{project_root}/channels/{channel}/active_production/{production_id}/assets/``
    (D-07, same pattern as Phase 9 audio).

    Args:
        channel: Channel name.
        production_id: Production identifier (e.g. ``"prod_001"``).

    Returns:
        Absolute ``Path`` to the temp asset directory.

    Raises:
        ValueError: If the channel name is invalid.
    """
    _validate_channel(channel)
    root = _project_root()
    return root / "channels" / channel / "active_production" / production_id / "assets"


# =========================================================================
# Metadata sidecar (D-09)
# =========================================================================


def asset_metadata_sidecar_path(asset_path: Path) -> Path:
    """Return the metadata sidecar path for a given asset file.

    Sidecar is a JSON file with the same name but ``.meta.json`` extension (D-09).

    Args:
        asset_path: Path to the asset file.

    Returns:
        ``Path`` with the extension replaced by ``.meta.json``.
    """
    return asset_path.with_suffix(".meta.json")
