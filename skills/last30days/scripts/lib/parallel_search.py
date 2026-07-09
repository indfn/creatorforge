"""Parallel AI web search for last30days skill.

Configurable via env vars:
  PARALLEL_BASE_URL      — Custom endpoint (default: https://api.parallel.ai/v1beta/search)
  PARALLEL_SEARCH_ENABLED — Set "false" to disable
"""

import os
import sys
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from . import http

# Configurable endpoint
ENDPOINT = os.getenv("PARALLEL_BASE_URL", "https://api.parallel.ai/v1beta/search")

EXCLUDED_DOMAINS = {
    "reddit.com", "www.reddit.com", "old.reddit.com",
    "twitter.com", "www.twitter.com", "x.com", "www.x.com",
}


def search_web(
    topic: str,
    from_date: str,
    to_date: str,
    api_key: str,
    depth: str = "default",
) -> List[Dict[str, Any]]:
    """Search the web via Parallel AI Search API.

    Args:
        topic: Search topic
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)
        api_key: Parallel AI API key
        depth: 'quick', 'default', or 'deep'

    Returns:
        List of result dicts

    Raises:
        http.HTTPError: On API errors
    """
    max_results = {"quick": 8, "default": 15, "deep": 25}.get(depth, 15)

    payload = {
        "objective": (
            f"Find recent blog posts, tutorials, news articles, and discussions "
            f"about {topic} from {from_date} to {to_date}. "
            f"Exclude reddit.com, x.com, and twitter.com."
        ),
        "max_results": max_results,
        "max_chars_per_result": 500,
    }

    sys.stderr.write(f"[Web] Searching Parallel AI for: {topic}\n")
    sys.stderr.flush()

    response = http.post(
        ENDPOINT,
        json_data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "parallel-beta": "search-extract-2025-10-10",
        },
        timeout=30,
    )

    return _normalize_results(response)


def _normalize_results(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Convert Parallel AI response to websearch item schema."""
    items = []

    results = response.get("results", [])
    if not isinstance(results, list):
        return items

    for i, result in enumerate(results):
        if not isinstance(result, dict):
            continue

        url = result.get("url", "")
        if not url:
            continue

        try:
            domain = urlparse(url).netloc.lower()
            if domain in EXCLUDED_DOMAINS:
                continue
            if domain.startswith("www."):
                domain = domain[4:]
        except Exception:
            domain = ""

        title = str(result.get("title", "")).strip()
        snippet = str(result.get("excerpt", result.get("snippet", result.get("description", "")))).strip()

        if not title and not snippet:
            continue

        relevance = result.get("relevance_score", result.get("relevance", 0.6))
        try:
            relevance = min(1.0, max(0.0, float(relevance)))
        except (TypeError, ValueError):
            relevance = 0.6

        items.append({
            "id": f"W{i+1}",
            "title": title[:200],
            "url": url,
            "source_domain": domain,
            "snippet": snippet[:500],
            "date": result.get("published_date", result.get("date")),
            "date_confidence": "med" if result.get("published_date") or result.get("date") else "low",
            "relevance": relevance,
            "why_relevant": str(result.get("summary", "")).strip()[:200],
        })

    sys.stderr.write(f"[Web] Parallel AI: {len(items)} results\n")
    sys.stderr.flush()

    return items