"""Temp asset lifecycle — manifest tracking and cleanup for per-scene audio/subtitle temp files.

Provides :class:`TempAssetManifest` for crash-safe tracking of generated audio, subtitle,
and alignment files, plus a cleanup handler for Phase 11's publish success callback.
"""

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from agent_core.core.validation import validate_or_raise

logger = logging.getLogger(__name__)

# Filename for the temp asset manifest within a production directory.
TEMP_MANIFEST_FILENAME = "temp_audio_manifest.json"


# =========================================================================
# Private helpers (standard pattern from publishing/uploader.py)
# =========================================================================


def _project_root() -> Path:
    """Resolve the project root directory (parent of ``agent_core/``)."""
    return Path(__file__).resolve().parent.parent.parent


def _validate_channel(channel: str) -> None:
    """Validate channel name to prevent path traversal.

    Raises:
        ValueError: If channel name contains invalid characters.
    """
    if not re.match(r"^[A-Za-z0-9_-]+$", channel):
        raise ValueError(
            f"Invalid channel name: {channel!r}. "
            "Only letters, numbers, hyphens, underscores allowed."
        )


def _production_dir(channel: str, production_id: str) -> Path:
    """Resolve the active production directory for a channel.

    Args:
        channel: Channel name (e.g. ``"ChannelA"``).
        production_id: Production identifier (e.g. ``"prod_001"``).

    Returns:
        Path to ``channels/{channel}/active_production/{production_id}/``.

    Raises:
        ValueError: If the channel name is invalid.
    """
    _validate_channel(channel)
    return _project_root() / "channels" / channel / "active_production" / production_id


# =========================================================================
# TempAssetManifest
# =========================================================================


class TempAssetManifest:
    """Tracks generated temp audio/subtitle assets for crash-safe cleanup.

    The manifest is persisted to ``{production_dir}/temp_audio_manifest.json``.
    Each ``add()`` call persists immediately to prevent data loss on crash
    (Pitfall 5 mitigation).  Cleanup deletes **only** files explicitly listed
    in the manifest — never by glob or pattern (Pitfall 5).

    Usage::

        manifest = TempAssetManifest(production_dir)
        manifest.add("scene_01", "/path/to/audio.wav", "audio")
        manifest.add_scene_assets("scene_01", audio_path, srt_path, vtt_path)
        deleted = manifest.cleanup()  # removes all tracked files + manifest
    """

    def __init__(self, production_dir: Path):
        """Initialise manifest for the given production directory.

        Automatically loads any existing manifest from disk.
        """
        self.production_dir = Path(production_dir).resolve()
        self.manifest_path = self.production_dir / TEMP_MANIFEST_FILENAME
        self.assets: list[dict] = []
        self._load()

    # ----- Persistence ----------------------------------------------------

    def _load(self) -> None:
        """Load existing manifest from disk, if present."""
        if not self.manifest_path.exists():
            return
        try:
            data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            self.assets = data.get("assets", [])
            logger.info("Loaded %d temp assets from manifest", len(self.assets))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(
                "Failed to parse manifest %s: %s — resetting",
                self.manifest_path,
                exc,
            )
            self.assets = []

    def _save(self) -> None:
        """Persist manifest to disk immediately."""
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "assets": self.assets,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self.manifest_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # ----- Asset tracking -------------------------------------------------

    def add(self, scene_id: str, file_path: str, asset_type: str) -> None:
        """Register a temp asset and persist the manifest immediately.

        Args:
            scene_id: Scene identifier (e.g. ``"scene_01"``).
            file_path: Absolute or relative path to the asset file.
            asset_type: One of ``"audio"``, ``"srt"``, ``"vtt"``, ``"alignment_json"``.
                Unknown types log a warning but are still added.
        """
        if asset_type not in ("audio", "srt", "vtt", "alignment_json"):
            logger.warning("Unknown asset type %r — still adding", asset_type)

        self.assets.append({
            "scene_id": scene_id,
            "file_path": str(Path(file_path).resolve()),
            "asset_type": asset_type,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        self._save()  # crash-safe: persist immediately (Pitfall 5)

    def add_scene_assets(
        self,
        scene_id: str,
        audio_path: str,
        srt_path: str,
        vtt_path: str,
        alignment_path: Optional[str] = None,
    ) -> None:
        """Convenience method: add all assets for a completed scene.

        Order: audio, alignment (if present), srt, vtt.
        Each call to :meth:`add` persists individually for crash safety.
        """
        self.add(scene_id, audio_path, "audio")
        if alignment_path:
            self.add(scene_id, alignment_path, "alignment_json")
        self.add(scene_id, srt_path, "srt")
        self.add(scene_id, vtt_path, "vtt")

    def get_assets(self, scene_id: Optional[str] = None) -> list[dict]:
        """Retrieve tracked assets, optionally filtered by scene ID.

        Args:
            scene_id: If given, return only assets for this scene.
                If ``None``, return all assets.

        Returns:
            A copy of the matching asset records.
        """
        if scene_id is None:
            return list(self.assets)
        return [a for a in self.assets if a.get("scene_id") == scene_id]

    # ----- Cleanup -------------------------------------------------------

    def cleanup(self) -> list[str]:
        """Delete all manifest-tracked files and the manifest itself.

        **Only** files listed in the manifest are deleted — never by glob
        or pattern (Pitfall 5).  Missing files are silently skipped.

        Returns:
            List of deleted file paths (including the manifest).
        """
        deleted: list[str] = []
        for asset in self.assets:
            path = Path(asset["file_path"])
            if path.exists():
                path.unlink()
                deleted.append(str(path))
                logger.info("Deleted temp asset: %s", path)
            else:
                logger.debug("Temp asset not found (already deleted): %s", path)

        # Delete manifest itself after all assets are removed.
        if self.manifest_path.exists():
            self.manifest_path.unlink()
            deleted.append(str(self.manifest_path))

        self.assets = []
        logger.info("Cleanup complete: removed %d files", len(deleted))
        return deleted

    # ----- Utilities -----------------------------------------------------

    def total_size_bytes(self) -> int:
        """Sum the file sizes of all tracked assets that still exist on disk.

        Returns:
            Total bytes, or ``0`` on any error.
        """
        total = 0
        for asset in self.assets:
            path = Path(asset["file_path"])
            if path.exists():
                try:
                    total += path.stat().st_size
                except OSError:
                    pass
        return total


# =========================================================================
# Module-level functions
# =========================================================================


def register_temp_cleanup(channel: str, production_id: str):
    """Register a cleanup handler for Phase 11's publish success callback.

    Returns a callable that, when invoked, cleans up all temp assets for the
    given production.  Phase 11 stores and calls this handler after a
    successful publish.

    Args:
        channel: Channel name (e.g. ``"ChannelA"``).
        production_id: Production identifier (e.g. ``"prod_001"``).

    Returns:
        A zero-argument callable that returns the number of deleted files.
    """
    prod_dir = _production_dir(channel, production_id)

    def _cleanup_handler():
        manifest = TempAssetManifest(prod_dir)
        deleted = manifest.cleanup()
        logger.info("Temp cleanup: removed %d files", len(deleted))
        return len(deleted)

    return _cleanup_handler


# =========================================================================
# CLI entry point
# =========================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Temp asset lifecycle management",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--production-dir", required=True)

    cleanup_parser = subparsers.add_parser("cleanup")
    cleanup_parser.add_argument("--production-dir", required=True)

    args = parser.parse_args()

    manifest = TempAssetManifest(Path(args.production_dir))

    if args.command == "list":
        assets = manifest.get_assets()
        if not assets:
            print("No temp assets tracked.")
        else:
            print(f"Tracking {len(assets)} temp assets:")
            for a in assets:
                print(f"  [{a['asset_type']}] {a['scene_id']}: {a['file_path']}")

    elif args.command == "cleanup":
        deleted = manifest.cleanup()
        print(f"Cleaned up {len(deleted)} temp files.")
