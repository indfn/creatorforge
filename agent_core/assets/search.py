"""Search query generation — translates scene script text into API search keywords."""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

_STOP_WORDS: frozenset[str] = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "shall", "can",
    "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "this", "that", "these", "those", "it", "its", "and", "or",
    "but", "not", "no", "nor", "so", "if", "then", "than",
    "just", "very", "too", "also", "about", "up", "out", "over",
})


def generate_search_query(
    scene_text: str,
    channel_pillars: Optional[list[str]] = None,
    max_keywords: int = 8,
) -> str:
    """Generate a stock API search query from scene script text.

    Extracts keywords by stripping punctuation, filtering stop words,
    and optionally appending channel pillar context keywords.

    Args:
        scene_text: The raw scene script text.
        channel_pillars: Optional list of channel content pillar keywords.
        max_keywords: Maximum number of keywords to include (default 8).

    Returns:
        A space-joined keyword string suitable for stock API search queries.
    """
    words = re.findall(r"[A-Za-z]{2,}", scene_text.lower())
    keywords = [w for w in words if w not in _STOP_WORDS and len(w) > 2]

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for kw in keywords:
        if kw not in seen:
            seen.add(kw)
            unique.append(kw)

    # Append channel pillar keywords for context
    if channel_pillars:
        pillar_words = " ".join(channel_pillars).lower().split()
        for pw in pillar_words:
            if pw not in seen:
                unique.append(pw)

    return " ".join(unique[:max_keywords])


def generate_sfx_query(
    scene_text: str,
    scene_emotion: Optional[str] = None,
) -> list[str]:
    """Generate SFX search query variants from scene action/emotion keywords.

    Returns up to 3 short query variants for the fallback chain to try.

    Args:
        scene_text: The raw scene script text.
        scene_emotion: Optional emotional/mood keyword (e.g. ``"suspense"``, ``"joyful"``).

    Returns:
        List of up to 3 query strings.
    """
    keywords = generate_search_query(scene_text, max_keywords=4).split()
    if not keywords:
        return ["ambient", "background", "atmosphere"]

    queries = [" ".join(keywords[:3])]
    if scene_emotion:
        queries.append(f"{scene_emotion} {' '.join(keywords[:2])}")
    if len(keywords) > 1:
        queries.append(" ".join(keywords[:2]))
    return list(dict.fromkeys(queries))
