"""Perplexity Sonar Pro web search via OpenRouter for last30days skill.

Configurable via env vars:
  OPENROUTER_BASE_URL  — Custom endpoint (default: https://openrouter.ai/api/v1/chat/completions)
  OPENROUTER_MODEL     — Model to use (default: perplexity/sonar-pro)
  OPENROUTER_SEARCH_ENABLED — Set "false" to disable
"""

import os
import re
import sys
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from . import http

# Configurable endpoint and model
ENDPOINT = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1/chat/completions")
MODEL = os.getenv("OPENROUTER_MODEL", "perplexity/sonar-pro")

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
    """Search the web via Perplexity Sonar Pro on OpenRouter.

    Args:
        topic: Search topic
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)
        api_key: OpenRouter API key
        depth: 'quick', 'default', or 'deep'

    Returns:
        List of result dicts

    Raises:
        http.HTTPError: On API errors
    """
    max_tokens = {"quick": 1024, "default": 2048, "deep": 4096}.get(depth, 2048)

    prompt = (
        f"Find recent blog posts, news articles, tutorials, and discussions "
        f"about {topic} published between {from_date} and {to_date}. "
        f"Exclude results from reddit.com, x.com, and twitter.com. "
        f"For each result, provide the title, URL, publication date, "
        f"and a brief summary of why it's relevant."
    )

    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
    }

    sys.stderr.write(f"[Web] Searching Sonar Pro via OpenRouter for: {topic}\n")
    sys.stderr.flush()

    response = http.post(
        ENDPOINT,
        json_data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://github.com/mvanhorn/last30days-openclaw",
            "X-Title": "last30days",
        },
        timeout=30,
    )

    return _normalize_results(response)


def _normalize_results(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Convert Sonar Pro response to websearch item schema."""
    items = []

    search_results = response.get("search_results", [])
    if isinstance(search_results, list) and search_results:
        items = _parse_search_results(search_results)

    if not items:
        citations = response.get("citations", [])
        content = _get_content(response)
        if isinstance(citations, list) and citations:
            items = _parse_citations(citations, content)

    sys.stderr.write(f"[Web] Sonar Pro: {len(items)} results\n")
    sys.stderr.flush()

    return items


def _parse_search_results(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    items = []
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
        if not title:
            continue
        date = result.get("date")
        date_confidence = "med" if date else "low"
        items.append({
            "id": f"W{i+1}",
            "title": title[:200],
            "url": url,
            "source_domain": domain,
            "snippet": str(result.get("snippet", result.get("description", ""))).strip()[:500],
            "date": date,
            "date_confidence": date_confidence,
            "relevance": 0.7,
            "why_relevant": "",
        })
    return items


def _parse_citations(citations: List[str], content: str) -> List[Dict[str, Any]]:
    items = []
    for i, url in enumerate(citations):
        if not isinstance(url, str) or not url:
            continue
        try:
            domain = urlparse(url).netloc.lower()
            if domain in EXCLUDED_DOMAINS:
                continue
            if domain.startswith("www."):
                domain = domain[4:]
        except Exception:
            domain = ""
        title = _extract_title_for_citation(content, i + 1) or domain
        items.append({
            "id": f"W{i+1}",
            "title": title[:200],
            "url": url,
            "source_domain": domain,
            "snippet": "",
            "date": None,
            "date_confidence": "low",
            "relevance": 0.6,
            "why_relevant": "",
        })
    return items


def _get_content(response: Dict[str, Any]) -> str:
    try:
        return response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return ""


def _extract_title_for_citation(content: str, index: int) -> Optional[str]:
    if not content:
        return None
    pattern = rf'\[{index}\][)\s]*([^\[\n]{{5,80}})'
    match = re.search(pattern, content)
    if match:
        title = match.group(1).strip().rstrip('.')
        title = re.sub(r'[*_`]', '', title)
        return title if len(title) > 3 else None
    return None