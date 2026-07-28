"""
Script splitter — parse multi-scene scripts into per-scene text segments.

Supports two scene-delimiter formats:
    1. ``[SCENE_N]`` markers (e.g. ``[SCENE_1]``, ``[SCENE 2]``) — one per scene.
    2. ``-- SCENE BREAK --`` lines — separates scenes by divider.

If no markers are found, the entire text is returned as a single scene.
"""

import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# Pattern for ``[SCENE_1]`` or ``[SCENE 1]`` markers (optionally followed by inline text).
_SCENE_MARKER_RE = re.compile(r"^\[SCENE[_ ](\d+)\](?:\s*(.+))?$", re.MULTILINE)

# Pattern for ``-- SCENE BREAK --`` divider lines.
_SCENE_BREAK_RE = re.compile(r"^--\s*SCENE\s*BREAK\s*--$", re.MULTILINE)


def split_script_text(text: str) -> list[dict]:
    """Split a plain-text script into per-scene segments.

    Scenes can be delimited by ``[SCENE_N]`` markers (preferred) or
    ``-- SCENE BREAK --`` lines.  If neither is found the entire text
    is returned as a single scene.

    Args:
        text: The raw script text.

    Returns:
        List of dicts, each with keys:
            ``scene_id`` (str, e.g. ``"scene_01"``),
            ``scene_number`` (int),
            ``text`` (str).
        Returns an empty list if the input is empty or whitespace-only.
    """
    text = text.strip()
    if not text:
        return []

    # Try ``[SCENE_N]`` markers first.
    matches = list(_SCENE_MARKER_RE.finditer(text))
    if matches:
        scenes = []
        for i, match in enumerate(matches):
            scene_num = int(match.group(1))
            inline_text = (match.group(2) or "").strip()

            # If the marker has inline text, use it.
            if inline_text:
                scene_text = inline_text
            else:
                # Gather text between this marker and the next (or end).
                start = match.end()
                end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
                scene_text = text[start:end].strip()

            scenes.append({
                "scene_id": f"scene_{scene_num:02d}",
                "scene_number": scene_num,
                "text": scene_text,
            })
        return scenes

    # Fall back to ``-- SCENE BREAK --`` markers.
    parts = _SCENE_BREAK_RE.split(text)
    parts = [p.strip() for p in parts if p.strip()]
    if parts:
        scenes = []
        for i, part in enumerate(parts):
            scenes.append({
                "scene_id": f"scene_{i + 1:02d}",
                "scene_number": i + 1,
                "text": part,
            })
        return scenes

    # No markers found — return the entire text as a single scene.
    return [
        {
            "scene_id": "scene_01",
            "scene_number": 1,
            "text": text,
        },
    ]


def split_script_from_json(path: Path) -> list[dict]:
    """Split a script from a JSON file into per-scene segments.

    Supports the following JSON structures:
        - ``{"scenes": [{"scene_id": "...", "text": "..."}, ...]}``
        - ``[{"scene_id": "...", "text": "..."}, ...]``
        - ``{"scenes": [{"say": ["Hello", "world"]}, ...]}`` (``filming_cards`` format)

    Args:
        path: Path to the JSON script file.

    Returns:
        List of scene dicts with ``scene_id``, ``scene_number``, ``text`` keys.
    """
    data = json.loads(path.read_text(encoding="utf-8"))

    # Normalize to a list of scene dicts.
    raw_scenes: list[dict] = []
    if isinstance(data, dict):
        raw_scenes = data.get("scenes", [])
    elif isinstance(data, list):
        raw_scenes = data

    scenes = []
    for i, scene in enumerate(raw_scenes):
        if not isinstance(scene, dict):
            continue

        scene_id = scene.get("scene_id", f"scene_{i + 1:02d}")
        scene_number = scene.get("scene_number", i + 1)

        # Extract text from various possible fields.
        text = scene.get("text", "")
        if not text and "say" in scene:
            say = scene["say"]
            if isinstance(say, list):
                text = " ".join(str(part) for part in say)
            elif isinstance(say, str):
                text = say

        scenes.append({
            "scene_id": scene_id,
            "scene_number": scene_number,
            "text": text,
        })

    return scenes


def write_scene_scripts(scenes: list[dict], output_dir: Path) -> list[Path]:
    """Write per-scene text files to the given output directory.

    Each scene is written as ``{output_dir}/{scene_id}_script.txt``.

    Args:
        scenes: List of scene dicts with ``scene_id`` and ``text`` keys.
        output_dir: Directory to write scene scripts into.

    Returns:
        List of written file paths.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for scene in scenes:
        scene_id = scene.get("scene_id", "unknown")
        text = scene.get("text", "")
        path = output_dir / f"{scene_id}_script.txt"
        path.write_text(text, encoding="utf-8")
        written.append(path)
        logger.debug("Wrote scene script: %s (%d chars)", path, len(text))

    logger.info("Wrote %d scene scripts to %s", len(written), output_dir)
    return written


def determine_source(path: Path) -> str:
    """Determine whether a script file is JSON or plain text.

    Reads the first non-whitespace character — if it is ``{`` or ``[``,
    returns ``"json"``; otherwise returns ``"text"``.

    Args:
        path: Path to the script file.

    Returns:
        ``"json"`` or ``"text"``.
    """
    content = path.read_text(encoding="utf-8").strip()
    if content.startswith("{") or content.startswith("["):
        return "json"
    return "text"
