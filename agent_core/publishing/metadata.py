"""SEO-optimized metadata generator for YouTube uploads.

Generates titles, descriptions, tags, and video snippet dicts using
LLM prompts with brand context from brain.json and channel_config.json
as grounding context.  Falls back to deterministic template-based
generation when the LLM is unavailable.

Usage:
    # Dry-run preview:
    python3 -m agent_core.publishing.metadata --channel ChannelA --dry-run

    # Persist generated metadata:
    python3 -m agent_core.publishing.metadata --channel ChannelA --save

    # Override description or chapters:
    python3 -m agent_core.publishing.metadata --channel ChannelA \\
        --description "Custom description..." --chapters-file ./chapters.txt
"""

import argparse
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from agent_core.recon.skeleton_ripper.llm_client import LLMClient

logger = logging.getLogger(__name__)

# =========================================================================
# Constants
# =========================================================================

YOUTUBE_CATEGORY_IDS: dict[str, str] = {
    "Education": "27",
    "Entertainment": "24",
    "Howto & Style": "26",
    "Science & Technology": "28",
    "Music": "10",
    "Gaming": "20",
    "News & Politics": "25",
    "People & Blogs": "22",
    "Comedy": "23",
    "Sports": "17",
    "Film & Animation": "1",
    "Autos & Vehicles": "2",
    "Pets & Animals": "15",
    "Travel & Events": "19",
    "Nonprofits & Activism": "29",
}

_DEFAULT_CTA = "Subscribe for more content like this!"
_DEFAULT_CATEGORY = "27"  # Education
_DESCRIPTION_MAX_CHARS = 5000
_CHAPTERS_MAX_CHARS = 5000

# =========================================================================
# Helpers
# =========================================================================


def _project_root() -> Path:
    """Resolve the project root directory (parent of ``agent_core/``)."""
    return Path(__file__).resolve().parent.parent.parent


def _validate_channel(channel: str) -> None:
    """Validate channel name to prevent path traversal.

    Only allows letters, digits, hyphens, and underscores.

    Raises:
        ValueError: If the channel name contains invalid characters.
    """
    if not re.match(r"^[A-Za-z0-9_-]+$", channel):
        raise ValueError(
            f"Invalid channel name: {channel!r}. "
            "Only letters, numbers, hyphens, underscores allowed."
        )


def _channel_config_path(channel: str) -> Path:
    _validate_channel(channel)
    return _project_root() / "channels" / channel / "channel_config.json"


def _brain_path(channel: str) -> Path:
    _validate_channel(channel)
    return _project_root() / "channels" / channel / "brain.json"


def _active_script_path(channel: str) -> Path:
    _validate_channel(channel)
    return _project_root() / "channels" / channel / "active_production" / "script.json"


def _active_metadata_path(channel: str) -> Path:
    _validate_channel(channel)
    return _project_root() / "channels" / channel / "active_production" / "metadata.json"


def _load_channel_config(channel: str) -> dict:
    """Load the per-channel configuration JSON, returning empty dict on failure."""
    config_path = _channel_config_path(channel)
    if not config_path.exists():
        logger.warning("Channel config not found: %s", config_path)
        return {}
    try:
        return json.loads(config_path.read_text())
    except (json.JSONDecodeError, OSError, ValueError) as e:
        logger.warning("Failed to parse channel config %s: %s", config_path, e)
        return {}


def _load_brain(channel: str) -> dict:
    """Load brain.json for the given channel, returning empty dict on failure."""
    brain_path = _brain_path(channel)
    if not brain_path.exists():
        logger.warning("brain.json not found: %s", brain_path)
        return {}
    try:
        return json.loads(brain_path.read_text())
    except (json.JSONDecodeError, OSError, ValueError) as e:
        logger.warning("Failed to parse brain.json %s: %s", brain_path, e)
        return {}


def _map_category(category_name: str) -> str:
    """Map a user-friendly category name to a YouTube numeric category ID.

    Returns ``"27"`` (Education) for unknown categories.
    """
    return YOUTUBE_CATEGORY_IDS.get(category_name, _DEFAULT_CATEGORY)


def _parse_duration(duration_str: str) -> int:
    """Convert a duration string (e.g. ``'30s'``, ``'2 min'``, ``'2-3 min'``)
    to seconds.

    Returns 90 if the string cannot be parsed.
    """
    if not duration_str:
        return 90
    duration_str = duration_str.strip().lower()

    # Try range pattern first: "2-3 min" → average = 150
    range_match = re.match(r"(\d+)\s*[-–]\s*(\d+)\s*(?:min|minute)s?", duration_str)
    if range_match:
        lo, hi = int(range_match.group(1)), int(range_match.group(2))
        return (lo + hi) // 2 * 60

    # Single number + unit: "30s", "2 min", "1 minute"
    single_match = re.match(r"(\d+)\s*(s|sec|second|m|min|minute)s?\b", duration_str)
    if single_match:
        value = int(single_match.group(1))
        unit = single_match.group(2)
        if unit in ("s", "sec", "second"):
            return value
        return value * 60

    # Plain number: "30" → assume seconds, "120" → assume seconds
    plain_match = re.match(r"^(\d+)$", duration_str)
    if plain_match:
        return int(plain_match.group(1))

    return 90


def _extract_script_summary(script_data: dict) -> str:
    """Build a concise text summary of the script for the LLM prompt.

    Args:
        script_data: The active_script.json dictionary.

    Returns:
        A human-readable summary string.
    """
    lines: list[str] = []

    title = script_data.get("title", "")
    if title:
        lines.append(f"Video Title: {title}")

    structure = script_data.get("script_structure", {})

    hook = structure.get("opening_hook", {}).get("hook_text", "")
    if hook:
        lines.append(f"Opening Hook: {hook}")

    intro = structure.get("intro_framework", {})
    proof = intro.get("proof", "")
    promise = intro.get("promise", "")
    if proof or promise:
        lines.append(f"Intro: {proof} | {promise}")

    sections = structure.get("sections", [])
    if sections:
        lines.append("Sections:")
        for sec in sections:
            title_sec = sec.get("title", "Untitled")
            points = sec.get("talking_points", [])
            points_str = "; ".join(points) if points else ""
            duration = sec.get("duration_estimate", "")
            line = f"  - {title_sec}"
            if points_str:
                line += f": {points_str}"
            if duration:
                line += f" [{duration}]"
            lines.append(line)

    mid_cta = structure.get("mid_cta", {}).get("text", "")
    if mid_cta:
        lines.append(f"Mid-video CTA: {mid_cta}")

    closing_cta = structure.get("closing_cta", {}).get("text", "")
    if closing_cta:
        lines.append(f"Closing CTA: {closing_cta}")

    outro = structure.get("outro", {})
    sub = outro.get("subscribe_prompt", "")
    tease = outro.get("next_video_tease", "")
    if sub or tease:
        lines.append(f"Outro: {sub} | {tease}")

    # Filming cards for scene structure
    cards = script_data.get("filming_cards", [])
    if cards:
        lines.append("Scenes:")
        for card in cards:
            sn = card.get("scene_number", "")
            sec_name = card.get("section_name", "")
            dur = card.get("duration_estimate", "")
            say = card.get("say", [])
            say_str = "; ".join(say[:2])  # first 2 points
            line = f"  - Scene {sn}: {sec_name}"
            if say_str:
                line += f" ({say_str})"
            if dur:
                line += f" [{dur}]"
            lines.append(line)

    return "\n".join(lines)


def _get_cta_text(brain_data: dict) -> str:
    """Extract the CTA strategy from brain data, falling back to default."""
    cta = brain_data.get("monetization", {}).get("cta_strategy", "")
    return cta.strip() if cta.strip() else _DEFAULT_CTA


def _build_full_description(
    base_desc: str,
    chapters: str,
    brain_data: dict,
) -> str:
    """Assemble the full YouTube description: LLM body → chapters → CTA.

    Args:
        base_desc: Description body from ``generate_metadata()``.
        chapters: Formatted chapter string from ``generate_chapters()``.
        brain_data: Brain data for CTA text extraction.

    Returns:
        Complete description string (may be truncated at ``_DESCRIPTION_MAX_CHARS``).
    """
    parts: list[str] = [base_desc.strip()]

    if chapters.strip():
        parts.append("")
        parts.append("---")
        parts.append("Chapters:")
        parts.append(chapters.strip())

    cta = _get_cta_text(brain_data)
    parts.append("")
    parts.append("---")
    parts.append(cta)

    full = "\n".join(parts)

    if len(full) > _DESCRIPTION_MAX_CHARS:
        logger.warning(
            "Description exceeds %d chars (%d); truncating.",
            _DESCRIPTION_MAX_CHARS,
            len(full),
        )
        full = full[:_DESCRIPTION_MAX_CHARS]
        # Truncate at word boundary to avoid cutting mid-word
        last_space = full.rfind(" ")
        if last_space > 0:
            full = full[:last_space]

    return full


# =========================================================================
# Template-based metadata generation (fallback when LLM unavailable)
# =========================================================================


def _generate_template_metadata(
    script_data: dict,
    brain_data: dict,
    category_id: str,
) -> dict:
    """Generate metadata using template/deterministic rules.

    Used when the LLM is not available (no API key, LLM_ENABLED=false,
    or the API call fails).

    Returns:
        Dict with keys ``title``, ``description``, ``tags``, ``category_id``.
    """
    # --- Title ---
    title = script_data.get("title", "Untitled Video")
    title = title.strip()[:100]

    # --- Tags ---
    tags: list[str] = []
    # From brain keywords
    keywords = brain_data.get("keywords", [])
    if isinstance(keywords, list):
        tags.extend(kw.strip() for kw in keywords if kw.strip())

    # From brain pillars
    pillars = brain_data.get("pillars", [])
    for pillar in pillars:
        if isinstance(pillar, str) and pillar.strip():
            tags.append(pillar.strip())

    # From ICP segments
    icp_segments = brain_data.get("icp", {}).get("segments", [])
    for seg in icp_segments:
        cleaned = seg.strip()
        if cleaned and cleaned not in tags:
            tags.append(cleaned)

    # From script structure sections
    structure = script_data.get("script_structure", {})
    sections = structure.get("sections", [])
    for sec in sections:
        sec_title = sec.get("title", "").strip()
        if sec_title and sec_title not in tags:
            tags.append(sec_title)

    # Deduplicate while preserving order
    seen: set[str] = set()
    deduped: list[str] = []
    for t in tags:
        if t.lower() not in seen:
            seen.add(t.lower())
            deduped.append(t)

    # Ensure within 500 total chars
    total_chars = sum(len(t) for t in deduped)
    while total_chars > 500 and deduped:
        last = deduped.pop()
        total_chars -= len(last)
    tags = deduped

    # --- Description ---
    desc_lines: list[str] = []

    hook = structure.get("opening_hook", {}).get("hook_text", "")
    if hook:
        desc_lines.append(hook)

    # Intro
    intro = structure.get("intro_framework", {})
    proof = intro.get("proof", "")
    promise = intro.get("promise", "")
    if proof and promise:
        desc_lines.append(f"In this video, {promise} {proof}")
    elif promise:
        desc_lines.append(f"In this video, {promise}")

    # Bullet points for sections
    if sections:
        desc_lines.append("")
        desc_lines.append("Here's what we'll cover:")
        for sec in sections:
            sec_title = sec.get("title", "").strip()
            if sec_title:
                desc_lines.append(f"• {sec_title}")

    # Value statement
    niche = brain_data.get("identity", {}).get("niche", "")
    differentiator = brain_data.get("identity", {}).get("differentiator", "")
    if differentiator:
        desc_lines.append("")
        desc_lines.append(differentiator)
    elif niche:
        desc_lines.append("")
        desc_lines.append(f"Brought to you by {niche}.")

    # Links placeholder
    desc_lines.append("")
    desc_lines.append("[LINKS_PLACEHOLDER]")

    description = "\n".join(desc_lines)

    return {
        "title": title,
        "description": description,
        "tags": tags,
        "category_id": category_id,
    }


# =========================================================================
# Public API
# =========================================================================


def generate_metadata(channel: str, script_data: dict, brain_data: dict) -> dict:
    """Generate SEO-optimised YouTube metadata using LLM (or template fallback).

    Loads brand context from ``channel_config.json``, builds a structured
    prompt from brain ICP/pillars/keywords, calls the configured LLM, and
    returns a validated metadata dict.

    Args:
        channel: Channel name (e.g. ``'ChannelA'``).
        script_data: The active ``script.json`` content (scenes, hooks, CTA).
        brain_data: The ``brain.json`` content (ICP, pillars, keywords).

    Returns:
        Dict with keys ``title``, ``description``, ``tags``, ``category_id``.
    """
    # Load channel config for brand context and category
    channel_config = _load_channel_config(channel)

    # Resolve category
    category_name = (
        channel_config.get("youtube", {})
        .get("upload_defaults", {})
        .get("category", "Education")
    )
    category_id = _map_category(category_name)

    # Try LLM generation first
    try:
        llm_enabled = os.getenv("LLM_ENABLED", "true").lower() in ("true", "1", "yes")
        api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")

        if llm_enabled and api_key:
            metadata = _generate_llm_metadata(
                channel_config, script_data, brain_data, category_id
            )
            if metadata is not None:
                return metadata

        logger.info("LLM unavailable; using template-based metadata generation.")
    except Exception as exc:
        logger.warning("LLM metadata generation failed: %s", exc)
        logger.info("Falling back to template-based metadata generation.")

    return _generate_template_metadata(script_data, brain_data, category_id)


def _generate_llm_metadata(
    channel_config: dict,
    script_data: dict,
    brain_data: dict,
    category_id: str,
) -> dict | None:
    """Generate metadata via LLM call with structured prompt.

    Returns ``None`` if the LLM call fails or the response cannot be parsed.
    """
    brand = channel_config.get("brand", {})
    brand_name = brand.get("name", "")
    brand_tagline = brand.get("tagline", "")
    brand_tone = brand.get("tone", "")  # tone hint from brand

    identity = brain_data.get("identity", {})
    tone = identity.get("tone", brand_tone or "")
    niche = identity.get("niche", "")
    differentiator = identity.get("differentiator", "")

    icp = brain_data.get("icp", {})
    segments = icp.get("segments", [])
    pain_points = icp.get("pain_points", [])
    goals = icp.get("goals", [])

    pillars = brain_data.get("pillars", [])
    keywords = brain_data.get("keywords", [])
    if not keywords:
        # Fallback: pillars + segments as keyword hints
        keywords = list(pillars) + list(segments)

    script_summary = _extract_script_summary(script_data)

    # Build system prompt
    system_prompt = (
        "You are an SEO metadata generator for YouTube content. "
        "Generate metadata that is accurate, includes relevant keywords, "
        "and drives click-through rate. "
        "Respond ONLY with a valid JSON object containing three keys: "
        '"title" (string, max 100 chars), '
        '"description_paragraphs" (list of strings — each paragraph is one element), '
        '"tags" (list of strings — total combined character count under 500). '
        "No markdown, no code fences, no extra text."
    )

    # Build user prompt with structured context
    ctx_parts: list[str] = ["Generate YouTube SEO metadata with the following context:\n"]

    if brand_name:
        ctx_parts.append(f"Channel/Brand: {brand_name}")
    if brand_tagline:
        ctx_parts.append(f"Tagline: {brand_tagline}")
    if niche:
        ctx_parts.append(f"Niche: {niche}")
    if tone:
        ctx_parts.append(f"Brand Tone / Voice: {tone}")
    if differentiator:
        ctx_parts.append(f"Differentiator: {differentiator}")

    if segments:
        ctx_parts.append(f"Target Audience Segments: {', '.join(segments)}")
    if pain_points:
        ctx_parts.append(f"Audience Pain Points: {', '.join(pain_points)}")
    if goals:
        ctx_parts.append(f"Audience Goals: {', '.join(goals)}")

    if pillars:
        ctx_parts.append(f"Content Pillars: {', '.join(pillars)}")

    if keywords:
        ctx_parts.append(f"SEO Keywords to consider: {', '.join(keywords[:15])}")

    ctx_parts.append(f"\n---\nVideo Script Summary:\n{script_summary}")

    ctx_parts.append(
        "\n\n---\nRequirements:\n"
        "- Title: SEO-optimised, under 100 characters, incorporates brand voice.\n"
        "- Description: First paragraph hooks the viewer with keywords. "
        "Then bullet points of what's covered. Include a [LINKS_PLACEHOLDER] "
        "marker where links will go. Do NOT include chapter markers.\n"
        "- Tags: Relevant keywords extracted from brain + script context, "
        "total combined length under 500 characters.\n"
        "Return ONLY valid JSON."
    )

    user_prompt = "\n".join(ctx_parts)

    client = LLMClient()
    response = client.chat(user_prompt=user_prompt, system_prompt=system_prompt)

    if not response or not response.strip():
        logger.warning("LLM returned empty response.")
        return None

    # Parse JSON — try to extract from possible markdown fences
    parsed = _parse_llm_json(response)
    if parsed is None:
        logger.warning("Failed to parse LLM response as JSON.")
        return None

    title = str(parsed.get("title", "")).strip()[:100]
    desc_paragraphs = parsed.get("description_paragraphs", [])
    tags_raw = parsed.get("tags", [])

    # Fallback for title
    if not title:
        title = script_data.get("title", "Untitled Video").strip()[:100]

    # Build description from paragraphs
    if isinstance(desc_paragraphs, list):
        description = "\n\n".join(str(p) for p in desc_paragraphs)
    elif isinstance(desc_paragraphs, str):
        description = desc_paragraphs
    else:
        description = ""

    if not description.strip():
        description = script_data.get("title", "Video description")

    # Process tags
    tags: list[str] = []
    if isinstance(tags_raw, list):
        for t in tags_raw:
            cleaned = str(t).strip()
            if cleaned:
                tags.append(cleaned)
    elif isinstance(tags_raw, str):
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()]

    # Enforce tag char limit
    total_chars = sum(len(t) for t in tags)
    while total_chars > 500 and tags:
        last = tags.pop()
        total_chars -= len(last)

    return {
        "title": title,
        "description": description,
        "tags": tags,
        "category_id": category_id,
    }


def _parse_llm_json(text: str) -> dict | None:
    """Attempt to parse a JSON object from LLM response text.

    Handles markdown code fences and trailing/leading whitespace.
    """
    # Strip code fences
    text = text.strip()
    if text.startswith("```"):
        # Remove opening fence (possibly with language hint)
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        # Remove closing fence
        text = re.sub(r"\n```\s*$", "", text)
        text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON with regex
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return None


def generate_chapters(scene_checkpoints: list[dict]) -> str:
    """Generate YouTube chapter markers from scene-level checkpoint data.

    Args:
        scene_checkpoints: List of checkpoint dicts, each containing at minimum
            ``scene_id`` (e.g. ``'scene_01'``).  May also contain ``output``
            with ``section_name``, ``title``, and/or ``duration_estimate`` keys.

    Returns:
        Formatted chapter string::

            00:00 - Intro
            01:30 - Main Content
            05:15 - Conclusion

        Returns empty string if ``scene_checkpoints`` is empty.
    """
    if not scene_checkpoints:
        return ""

    # Extract scene info from checkpoints
    scenes: list[dict] = []
    for cp in scene_checkpoints:
        output = cp.get("output", cp)  # support both flat and nested shapes
        if isinstance(output, dict):
            sid = cp.get("scene_id", output.get("scene_id", ""))
        else:
            sid = cp.get("scene_id", "")

        # Extract scene number from scene_id
        scene_num = 0
        if sid:
            num_match = re.search(r"(\d+)", sid)
            if num_match:
                scene_num = int(num_match.group(1))

        scene_label = (
            output.get("section_name")
            or output.get("title")
            or cp.get("section_name")
            or sid
            or "Untitled"
        )

        duration_str = (
            output.get("duration_estimate")
            or cp.get("duration_estimate")
            or ""
        )

        scenes.append({
            "scene_number": scene_num,
            "label": scene_label,
            "duration_seconds": _parse_duration(duration_str),
        })

    # Sort by scene number
    scenes.sort(key=lambda s: s["scene_number"])

    # Build chapter lines with running timestamps
    running_seconds = 0
    lines: list[str] = []
    for scene in scenes:
        minutes = running_seconds // 60
        seconds = running_seconds % 60
        timestamp = f"{minutes:02d}:{seconds:02d}"
        lines.append(f"{timestamp} - {scene['label']}")
        running_seconds += scene["duration_seconds"]

    chapters_str = "\n".join(lines)

    # Enforce YouTube chapter limit (~5000 chars total for description)
    if len(chapters_str) > _CHAPTERS_MAX_CHARS:
        logger.warning(
            "Chapters string exceeds %d chars; truncating.",
            _CHAPTERS_MAX_CHARS,
        )
        # Truncate to last complete line
        truncated = ""
        for line in lines:
            candidate = f"{truncated}{line}\n" if truncated else f"{line}\n"
            if len(candidate) > _CHAPTERS_MAX_CHARS - 3:  # leave room for "..."
                truncated = truncated.rstrip("\n") + "\n..."
                break
            truncated = candidate
        chapters_str = truncated.strip()

    return chapters_str


def build_video_snippet(
    metadata: dict,
    chapters: str,
    channel_config: dict,
    brain_data: dict | None = None,
) -> dict:
    """Build the full YouTube API video snippet dict for ``videos().insert()``.

    Args:
        metadata: Output from ``generate_metadata()`` — dict with keys
            ``title``, ``description``, ``tags``, ``category_id``.
        chapters: Output from ``generate_chapters()`` — formatted chapter string.
        channel_config: Parsed ``channel_config.json`` dict.
        brain_data: Optional brain data for CTA text extraction; falls back to
            empty dict if not provided.

    Returns:
        Dict structured for ``youtube.videos().insert(part="snippet,status", body=...)``.
    """
    if brain_data is None:
        brain_data = {}

    # Assemble full description with chapters and CTA
    full_desc = _build_full_description(
        base_desc=metadata.get("description", ""),
        chapters=chapters,
        brain_data=brain_data,
    )

    # Resolve defaults
    upload_defaults = channel_config.get("youtube", {}).get("upload_defaults", {})
    defaults_section = channel_config.get("defaults", {})

    language = upload_defaults.get("language", "en")
    privacy = (
        defaults_section.get("privacy")
        or upload_defaults.get("visibility", "private")
    )
    embeddable = defaults_section.get("embed", True)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    return {
        "snippet": {
            "title": metadata.get("title", ""),
            "description": full_desc,
            "tags": metadata.get("tags", []),
            "categoryId": metadata.get("category_id", _DEFAULT_CATEGORY),
            "defaultLanguage": language,
            "defaultAudioLanguage": language,
        },
        "status": {
            "privacyStatus": privacy,
            # publishAt is added conditionally by the uploader; do NOT set
            # it to None here — the YouTube API may reject null values.
            "selfDeclaredMadeForKids": False,
            "embeddable": embeddable,
        },
        "recordingDetails": {
            "location": {
                "latitude": 0.0,
                "longitude": 0.0,
                "altitude": 0.0,
                "locationDescription": "",
            },
            "recordingDate": now,
        },
    }


def generate_full_metadata(
    channel: str,
    pipeline_id: str | None = None,
    description_override: str | None = None,
    chapters_file: str | Path | None = None,
    script_data: dict | None = None,
    brain_data: dict | None = None,
    channel_config: dict | None = None,
    scene_checkpoints: list[dict] | None = None,
) -> dict:
    """Convenience wrapper: load data, generate metadata, build and return snippet.

    This is the main entry point for programmatic callers (e.g. ``uploader.py``).

    Args:
        channel: Channel name (e.g. ``'ChannelA'``).
        pipeline_id: Optional pipeline ID for reading scene checkpoints.
        description_override: If provided, replaces the auto-generated description.
        chapters_file: Path to a custom chapters text file (one ``MM:SS - Label``
            per line). Overrides auto-generated chapters.
        script_data: Pre-loaded script data; auto-loaded if ``None``.
        brain_data: Pre-loaded brain data; auto-loaded if ``None``.
        channel_config: Pre-loaded channel config; auto-loaded if ``None``.
        scene_checkpoints: Pre-loaded scene checkpoints; loaded from pipeline
            if ``None`` and ``pipeline_id`` is provided.

    Returns:
        The full YouTube API snippet dict (same structure as
        ``build_video_snippet()``).
    """
    # Load data if not provided
    if channel_config is None:
        channel_config = _load_channel_config(channel)
    if brain_data is None:
        brain_data = _load_brain(channel)
    if script_data is None:
        script_path = _active_script_path(channel)
        if script_path.exists():
            try:
                script_data = json.loads(script_path.read_text())
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to load active script: %s", e)
                script_data = {}
        else:
            logger.warning("Active script not found at %s", script_path)
            script_data = {}

    # Generate metadata
    metadata = generate_metadata(channel, script_data, brain_data)

    # Override description if provided
    if description_override is not None:
        metadata["description"] = description_override

    # Generate chapters
    chapters = ""
    if chapters_file is not None:
        # Read from custom file
        chapters_path = Path(chapters_file)
        if chapters_path.exists():
            chapters = chapters_path.read_text().strip()
        else:
            logger.warning("Chapters file not found: %s", chapters_path)
    elif scene_checkpoints is not None:
        chapters = generate_chapters(scene_checkpoints)
    elif pipeline_id is not None:
        # Load checkpoints from CheckpointManager
        try:
            from agent_core.core.checkpoint import CheckpointManager

            cm = CheckpointManager()
            checkpoints = cm.list_checkpoints(pipeline_id)
            if checkpoints:
                # Convert Checkpoint objects to dicts for generate_chapters
                scene_checkpoints = []
                for cp in checkpoints:
                    cp_dict = {
                        "scene_id": cp.scene_id or "",
                        "output": cp.output,
                    }
                    scene_checkpoints.append(cp_dict)
                chapters = generate_chapters(scene_checkpoints)
        except Exception as exc:
            logger.warning("Failed to load checkpoints for pipeline %s: %s", pipeline_id, exc)

    # Build the snippet
    snippet = build_video_snippet(metadata, chapters, channel_config, brain_data)

    return snippet


# =========================================================================
# Backward-compatible stubs (delegate to generate_metadata)
# =========================================================================


def generate_title(channel: str, script_data: dict) -> str:
    """Legacy wrapper — returns title from ``generate_metadata()``.

    Args:
        channel: Channel name.
        script_data: The active ``script.json`` content.

    Returns:
        Title string (under 100 characters).
    """
    brain = _load_brain(channel)
    result = generate_metadata(channel, script_data, brain)
    return result["title"]


def generate_description(channel: str, script_data: dict) -> str:
    """Legacy wrapper — returns description from ``generate_metadata()``.

    Args:
        channel: Channel name.
        script_data: The active ``script.json`` content.

    Returns:
        Description string.
    """
    brain = _load_brain(channel)
    result = generate_metadata(channel, script_data, brain)
    return result["description"]


def generate_tags(channel: str, script_data: dict) -> list[str]:
    """Legacy wrapper — returns tags list from ``generate_metadata()``.

    Args:
        channel: Channel name.
        script_data: The active ``script.json`` content.

    Returns:
        List of tag strings (total under 500 characters).
    """
    brain = _load_brain(channel)
    result = generate_metadata(channel, script_data, brain)
    return result["tags"]


# =========================================================================
# CLI Entry Point
# =========================================================================


def main() -> None:
    """CLI entry point for YouTube metadata generation.

    Supports ``--dry-run`` preview, ``--save`` persistence, and
    ``--description`` / ``--chapters-file`` overrides.
    """
    parser = argparse.ArgumentParser(
        description="Generate YouTube video SEO metadata",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--channel",
        required=True,
        help="Channel name (e.g. ChannelA)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview generated metadata without persisting",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Persist generated metadata to metadata.json (only relevant with --dry-run)",
    )
    parser.add_argument(
        "--description",
        help="Override auto-generated description",
    )
    parser.add_argument(
        "--chapters-file",
        type=Path,
        help="Path to custom chapters file (overrides auto-generation)",
    )
    parser.add_argument(
        "--pipeline-id",
        help="Pipeline ID for chapter checkpoint reading",
    )
    args = parser.parse_args()

    # Validate channel name for path traversal safety
    try:
        _validate_channel(args.channel)
    except ValueError as e:
        print(f"Error: {e}")
        exit(1)

    # Load config and brain
    channel_config = _load_channel_config(args.channel)
    brain_data = _load_brain(args.channel)

    # Find active script
    script_path = _active_script_path(args.channel)
    if script_path.exists():
        try:
            script_data = json.loads(script_path.read_text())
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load active script: %s", e)
            script_data = {}
    else:
        logger.warning("Active script not found at %s — using empty data", script_path)
        script_data = {}

    # Generate metadata
    metadata = generate_metadata(args.channel, script_data, brain_data)

    # Override description if provided
    if args.description is not None:
        metadata["description"] = args.description

    # Generate chapters
    chapters_text = ""
    if args.chapters_file is not None:
        if args.chapters_file.exists():
            chapters_text = args.chapters_file.read_text().strip()
        else:
            logger.warning("Chapters file not found: %s", args.chapters_file)
    elif args.pipeline_id is not None:
        try:
            from agent_core.core.checkpoint import CheckpointManager

            cm = CheckpointManager()
            checkpoints = cm.list_checkpoints(args.pipeline_id)
            scene_cps = []
            for cp in checkpoints:
                scene_cps.append({
                    "scene_id": cp.scene_id or "",
                    "output": cp.output,
                })
            chapters_text = generate_chapters(scene_cps)
        except Exception as exc:
            logger.warning("Failed to load checkpoints: %s", exc)

    # Build snippet
    snippet = build_video_snippet(metadata, chapters_text, channel_config, brain_data)

    # Print timestamp for audit
    now_str = datetime.now(timezone.utc).isoformat()

    if args.dry_run:
        print(
            json.dumps(
                {
                    "channel": args.channel,
                    "generated_at": now_str,
                    "dry_run": True,
                    "snippet": snippet,
                },
                indent=2,
            )
        )
        if args.save:
            meta_path = _active_metadata_path(args.channel)
            meta_path.parent.mkdir(parents=True, exist_ok=True)
            metadata_output = {
                "title": metadata.get("title", ""),
                "description": metadata.get("description", ""),
                "tags": metadata.get("tags", []),
                "category_id": metadata.get("category_id", "27"),
                "generated_at": now_str,
                "channel": args.channel,
            }
            meta_path.write_text(json.dumps(metadata_output, indent=2))
            print(f"\nMetadata saved to {meta_path}")
    else:
        # Persist metadata
        meta_path = _active_metadata_path(args.channel)
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_output = {
            "title": metadata.get("title", ""),
            "description": metadata.get("description", ""),
            "tags": metadata.get("tags", []),
            "category_id": metadata.get("category_id", "27"),
            "generated_at": now_str,
            "channel": args.channel,
        }
        meta_path.write_text(json.dumps(metadata_output, indent=2))
        print(f"Metadata saved to {meta_path}")
        print(json.dumps(snippet, indent=2))


if __name__ == "__main__":
    main()
