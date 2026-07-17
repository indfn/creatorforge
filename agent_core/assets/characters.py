"""Character SVG model resolution and variant lookup.

Characters are first-class consistent assets (PROD-VISUAL-06). Each character
lives in a directory with::

    metadata.json     — {name, variants: {variant_name: filename.svg}, tags, default_variant}
    {variant}.svg     — One SVG file per variant

Scene scripts reference characters as::

    [char:name]         — Resolves to default_variant
    [char:name:variant] — Resolves to specific variant

Lookup order (D-05):
    1. Channel override: ``channels/{channel}/assets/characters/{name}/``
    2. Global library:  ``assets/consistent/global/characters/{name}/``
"""

import json
import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class CharacterResolver:
    """Resolves character SVG paths by name and optional variant.

    Args:
        channel: Channel name for per-channel override lookups.
            Only letters, numbers, hyphens, underscores allowed.

    Raises:
        ValueError: If *channel* contains invalid characters.
    """

    def __init__(self, channel: str) -> None:
        self._validate_channel(channel)
        self.channel = channel
        self.project_root = Path(__file__).resolve().parent.parent.parent

    # -----------------------------------------------------------------
    # Channel validation
    # -----------------------------------------------------------------

    @staticmethod
    def _validate_channel(channel: str) -> None:
        """Validate channel name to prevent path traversal (T-10-05).

        Raises:
            ValueError: If *channel* contains characters outside
                ``[A-Za-z0-9_-]``.
        """
        if not re.match(r"^[A-Za-z0-9_-]+$", channel):
            raise ValueError(
                f"Invalid channel name: {channel!r}. "
                "Only letters, numbers, hyphens, underscores allowed."
            )

    # -----------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------

    def resolve(self, name: str, variant: Optional[str] = None) -> Optional[Path]:
        """Resolve the filesystem path to a character SVG.

        Lookup order (D-05):
            1. Channel override: ``channels/{channel}/assets/characters/{name}/``
            2. Global library:  ``assets/consistent/global/characters/{name}/``

        Args:
            name: Character directory name (e.g. ``"Anna"``, ``"D-19"``).
            variant: Optional variant key (e.g. ``"happy"``, ``"serious"``).
                If ``None``, the character's ``default_variant`` is used.

        Returns:
            Absolute ``Path`` to the SVG file, or ``None`` if the character
            or requested variant could not be found.

        Notes:
            - Never raises (T-10-06). Logs a warning on failure.
            - Logs the character name and channel, not the full resolved path
              (T-10-07).
        """
        # Priority 1: Channel override
        channel_dir = (
            self.project_root
            / "channels"
            / self.channel
            / "assets"
            / "characters"
            / name
        )
        result = self._find_character(channel_dir, name, variant)
        if result is not None:
            return result

        # Priority 2: Global library
        global_dir = (
            self.project_root
            / "assets"
            / "consistent"
            / "global"
            / "characters"
            / name
        )
        result = self._find_character(global_dir, name, variant)
        if result is not None:
            return result

        logger.warning(
            "Character '%s' not found for channel '%s' "
            "(checked channel override and global library)",
            name,
            self.channel,
        )
        return None

    def list_characters(self) -> list[dict]:
        """Scan both global and channel character directories.

        Returns:
            List of metadata dicts, each augmented with an ``"path"`` key.
            Returns ``[]`` if no character directories exist. Never raises.
        """
        results: list[dict] = []

        # Global directory
        global_dir = (
            self.project_root / "assets" / "consistent" / "global" / "characters"
        )
        results.extend(self._scan_character_dir(global_dir))

        # Channel override directory
        channel_dir = (
            self.project_root / "channels" / self.channel / "assets" / "characters"
        )
        results.extend(self._scan_character_dir(channel_dir))

        return results

    # -----------------------------------------------------------------
    # Internals
    # -----------------------------------------------------------------

    def _find_character(
        self,
        char_dir: Path,
        name: str,
        variant: Optional[str] = None,
    ) -> Optional[Path]:
        """Look up a character SVG in *char_dir*, consulting metadata.json.

        Resolution rules:
            - If ``char_dir/metadata.json`` exists and is valid JSON:
                1. Use *variant* if provided, else ``default_variant`` from
                   metadata (or ``"default"`` fallback).
                2. Look up SVG filename in ``variants`` dict if present.
                3. Fall back to ``{variant_name}.svg`` as the filename.
            - If ``metadata.json`` does **not** exist:
                Fall back to ``{name}.svg`` (backward compatibility).
            - If the resolved SVG file does not exist on disk → ``None``.

        Returns:
            Absolute ``Path`` to the SVG, or ``None``.
        """
        if not char_dir.is_dir():
            return None

        meta_path = char_dir / "metadata.json"

        if meta_path.is_file():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning(
                    "Corrupted or unreadable metadata for character '%s': %s",
                    name,
                    exc,
                )
                return None

            # Determine which variant to look up
            variant_name: str = variant or meta.get("default_variant", "default")

            # Look up SVG filename from variants dict, or fall back to {name}.svg
            variants: dict = meta.get("variants", {})
            svg_filename: str = variants.get(variant_name, f"{variant_name}.svg")

            svg_path = char_dir / svg_filename
            if svg_path.is_file():
                return svg_path.resolve()

            logger.warning(
                "Variant '%s' not found for character '%s' (channel '%s')",
                variant_name,
                name,
                self.channel,
            )
            return None

        # No metadata.json — fall back to {name}.svg
        fallback = char_dir / f"{name}.svg"
        if fallback.is_file():
            return fallback.resolve()

        return None

    def _scan_character_dir(self, char_dir: Path) -> list[dict]:
        """Scan a single character directory, reading metadata for each entry.

        Args:
            char_dir: Path to a ``characters/`` directory (global or channel).

        Returns:
            List of metadata dicts (one per subdirectory), each augmented
            with ``"path"`` set to the subdirectory's string path.
            Returns ``[]`` if *char_dir* doesn't exist or is empty.
            Skips entries with unreadable metadata (logs a warning).
        """
        if not char_dir.is_dir():
            return []

        entries: list[dict] = []
        for entry in sorted(char_dir.iterdir()):
            if not entry.is_dir():
                continue

            meta_file = entry / "metadata.json"
            if not meta_file.is_file():
                continue

            try:
                meta: dict = json.loads(meta_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning(
                    "Skipping character directory '%s': %s",
                    entry.name,
                    exc,
                )
                continue

            meta["path"] = str(entry)
            entries.append(meta)

        return entries
