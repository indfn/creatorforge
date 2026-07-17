"""
Test fixtures and mocks for visual asset pipeline tests.

Provides mock API response fixtures (Pexels, Pixabay, Freesound),
a fixture to remove stock API key env vars, and a temporary cache fixture.
"""

import json
from pathlib import Path

import pytest


# =========================================================================
# Mock API response fixtures
# =========================================================================


@pytest.fixture
def mock_pexels_video_response():
    """Return a mock Pexels API video search response.

    Matches ``GET /v1/videos/search`` response format with one HD video result.
    """
    return {
        "videos": [
            {
                "id": 12345,
                "width": 1920,
                "height": 1080,
                "duration": 15,
                "user": {"name": "Test Photographer"},
                "video_files": [
                    {"quality": "hd", "link": "https://example.com/video.mp4",
                     "width": 1920, "height": 1080},
                    {"quality": "sd", "link": "https://example.com/video_sd.mp4",
                     "width": 640, "height": 360},
                ],
            }
        ]
    }


@pytest.fixture
def mock_pixabay_video_response():
    """Return a mock Pixabay API video search response.

    Matches ``GET /api/videos/`` response format with ``hits[].videos.medium.url``.
    """
    return {
        "totalHits": 1,
        "hits": [
            {
                "id": 67890,
                "pageURL": "https://pixabay.com/videos/test-123/",
                "type": "video",
                "tags": "ocean, waves, beach",
                "duration": 12,
                "videos": {
                    "medium": {
                        "url": "https://example.com/pixabay_medium.mp4",
                        "width": 1920,
                        "height": 1080,
                        "size": 2500000,
                    },
                    "small": {
                        "url": "https://example.com/pixabay_small.mp4",
                        "width": 640,
                        "height": 360,
                        "size": 800000,
                    },
                    "tiny": {
                        "url": "https://example.com/pixabay_tiny.mp4",
                        "width": 480,
                        "height": 270,
                        "size": 300000,
                    },
                },
                "user_id": 123456,
                "user": "TestPhotographer",
                "imageWidth": 1920,
                "imageHeight": 1080,
            }
        ],
        "total": 1,
    }


@pytest.fixture
def mock_freesound_response():
    """Return a mock Freesound API search response.

    Matches ``GET /apiv2/search/`` response format with ``results[].previews``.
    Uses preview-hq-mp3 URLs (Pitfall 5 — no OAuth2 required).
    """
    return {
        "count": 1,
        "results": [
            {
                "id": 123456,
                "name": "ocean_waves",
                "tags": ["ocean", "waves", "water", "nature"],
                "duration": 8.5,
                "license": "Creative Commons 0",
                "username": "sounddesigner",
                "previews": {
                    "preview-hq-mp3": "https://example.com/sound_hq.mp3",
                    "preview-lq-mp3": "https://example.com/sound_lq.mp3",
                    "preview-hq-ogg": "https://example.com/sound_hq.ogg",
                    "preview-lq-ogg": "https://example.com/sound_lq.ogg",
                },
            }
        ],
        "next": None,
        "previous": None,
    }


# =========================================================================
# Environment isolation
# =========================================================================


@pytest.fixture
def disable_stock_api_keys(monkeypatch):
    """Remove stock API key environment variables so providers skip cleanly.

    After applying this fixture:
        - ``PexelsProvider`` initialises with ``api_key=""``
        - ``PixabayProvider`` initialises with ``api_key=""``
        - ``FreesoundProvider`` initialises with ``api_key=""``
    """
    for key in ("PEXELS_API_KEY", "PIXABAY_API_KEY", "FREESOUND_API_KEY"):
        monkeypatch.delenv(key, raising=False)


# =========================================================================
# Temporary cache fixture
# =========================================================================


@pytest.fixture
def sample_asset_cache(tmp_path):
    """Create a temporary SQLite AssetCache for testing.

    Returns:
        ``AssetCache`` instance backed by a temp file at ``{tmp_path}/test_cache.db``.
    """
    from agent_core.assets.cache import AssetCache

    db_path = tmp_path / "test_cache.db"
    return AssetCache(db_path)
