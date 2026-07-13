"""Mock-based tests for scripts/fetch-yt-analytics.py.

Tests cover: Data API parsing, Analytics API parsing, duration parsing,
thumbnail chain, OAuth token handling, error recovery, quota handling.
"""

import json
from unittest.mock import Mock, patch

import pytest


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    """Prevent tests from touching real .env or token files."""
    monkeypatch.delenv("YOUTUBE_DATA_API_KEY", raising=False)
    monkeypatch.setenv("YOUTUBE_DATA_API_KEY", "test-api-key")
    # Mock token path to a non-existent temp file
    monkeypatch.setattr("scripts.fetch_yt_analytics.TOKEN_PATH",
                        "/tmp/no-such-token.json")


@pytest.fixture
def mock_response():
    """Build a mock requests.Response with .json() and .raise_for_status()."""
    def _build(status=200, json_data=None, raise_error=None):
        resp = Mock()
        resp.status_code = status
        resp.json.return_value = json_data or {}
        if raise_error:
            from requests.exceptions import HTTPError
            resp.raise_for_status.side_effect = HTTPError(response=resp)
        else:
            resp.raise_for_status.return_value = None
        return resp
    return _build


# ── Duration Parsing ─────────────────────────────────────────────────


@pytest.mark.parametrize("duration_str,expected", [
    ("PT0S", 0),
    ("PT2M45S", 165),
    ("PT1H2M30S", 3750),
    ("PT30S", 30),
    ("PT5M", 300),
    ("PT1H", 3600),
    ("PT1H30M", 5400),
    ("", 0),
    ("invalid", 0),
])
def test_parse_iso8601_duration(duration_str, expected):
    """ISO 8601 durations correctly parse to seconds."""
    from scripts.fetch_yt_analytics import parse_iso8601_duration
    assert parse_iso8601_duration(duration_str) == expected


# ── Data API (fetch_data_api) ────────────────────────────────────────


class TestFetchDataApi:
    """Tests for fetch_data_api()."""

    def test_successful_fetch(self, mock_response):
        """Returns parsed metrics dict from a valid API response."""
        from scripts.fetch_yt_analytics import fetch_data_api

        api_data = {
            "items": [{
                "statistics": {
                    "viewCount": "15000",
                    "likeCount": "1200",
                    "commentCount": "85",
                },
                "snippet": {
                    "title": "Test Video",
                    "publishedAt": "2026-07-10T12:00:00Z",
                    "thumbnails": {
                        "high": {"url": "https://img.youtube.com/vi/abc/hqdefault.jpg"},
                        "default": {"url": "https://img.youtube.com/vi/abc/default.jpg"},
                    },
                },
                "contentDetails": {
                    "duration": "PT10M30S",
                },
            }]
        }

        with patch("scripts.fetch_yt_analytics.requests.get",
                   return_value=mock_response(json_data=api_data)):
            result = fetch_data_api("test_video_id", "test-api-key")

        assert result is not None
        assert result["title"] == "Test Video"
        assert result["views"] == 15000
        assert result["likes"] == 1200
        assert result["comments"] == 85
        assert result["duration_seconds"] == 630
        assert result["format"] == "youtube_longform"  # > 180s
        assert result["thumbnail_url"] == "https://img.youtube.com/vi/abc/hqdefault.jpg"
        assert result["published_at"] == "2026-07-10T12:00:00Z"

    def test_short_duration_shorts_format(self, mock_response):
        """Duration <= 180s produces youtube_shorts format."""
        from scripts.fetch_yt_analytics import fetch_data_api

        api_data = {
            "items": [{
                "statistics": {"viewCount": "500"},
                "snippet": {"title": "Short", "publishedAt": "2026-07-10T12:00:00Z"},
                "contentDetails": {"duration": "PT45S"},
            }]
        }

        with patch("scripts.fetch_yt_analytics.requests.get",
                   return_value=mock_response(json_data=api_data)):
            result = fetch_data_api("short_id", "test-api-key")

        assert result["format"] == "youtube_shorts"

    def test_empty_items_returns_none(self, mock_response):
        """Empty items list returns None (video not found)."""
        from scripts.fetch_yt_analytics import fetch_data_api

        api_data = {"items": []}

        with patch("scripts.fetch_yt_analytics.requests.get",
                   return_value=mock_response(json_data=api_data)):
            result = fetch_data_api("nonexistent_id", "test-api-key")

        assert result is None

    def test_thumbnail_fallback_chain(self, mock_response):
        """Picks highest resolution thumbnail (maxres > high > medium > default)."""
        from scripts.fetch_yt_analytics import fetch_data_api

        api_data = {
            "items": [{
                "statistics": {"viewCount": "0"},
                "snippet": {
                    "title": "Thumb Test",
                    "publishedAt": "2026-07-10T12:00:00Z",
                    "thumbnails": {
                        "default": {"url": "https://img.youtube.com/vi/abc/default.jpg"},
                        "medium": {"url": "https://img.youtube.com/vi/abc/mqdefault.jpg"},
                    },
                },
                "contentDetails": {"duration": "PT60S"},
            }]
        }

        with patch("scripts.fetch_yt_analytics.requests.get",
                   return_value=mock_response(json_data=api_data)):
            result = fetch_data_api("thumb_id", "test-api-key")

        assert result["thumbnail_url"] == "https://img.youtube.com/vi/abc/mqdefault.jpg"

    def test_missing_thumbnail(self, mock_response):
        """No thumbnails in response returns None for thumbnail_url."""
        from scripts.fetch_yt_analytics import fetch_data_api

        api_data = {
            "items": [{
                "statistics": {"viewCount": "0"},
                "snippet": {"title": "No Thumb", "publishedAt": "2026-07-10T12:00:00Z"},
                "contentDetails": {"duration": "PT30S"},
            }]
        }

        with patch("scripts.fetch_yt_analytics.requests.get",
                   return_value=mock_response(json_data=api_data)):
            result = fetch_data_api("no_thumb", "test-api-key")

        assert result["thumbnail_url"] is None

    def test_http_error_raises(self, mock_response):
        """HTTP errors propagate (caller handles them)."""
        from scripts.fetch_yt_analytics import fetch_data_api
        from requests.exceptions import HTTPError

        with patch("scripts.fetch_yt_analytics.requests.get",
                   return_value=mock_response(status=403, raise_error=True)):
            with pytest.raises(HTTPError):
                fetch_data_api("error_id", "test-api-key")


# ── Analytics API (fetch_analytics_api) ──────────────────────────────


class TestFetchAnalyticsApi:
    """Tests for fetch_analytics_api()."""

    def test_successful_fetch(self, mock_response):
        """Returns parsed analytics metrics from a valid response."""
        from scripts.fetch_yt_analytics import fetch_analytics_api

        analytics_data = {
            "rows": [[5000, 120.5, 25]],
            "columnHeaders": [
                {"name": "estimatedMinutesWatched"},
                {"name": "averageViewDuration"},
                {"name": "subscribersGained"},
            ],
        }

        with patch("scripts.fetch_yt_analytics.requests.get",
                   return_value=mock_response(json_data=analytics_data)):
            result = fetch_analytics_api(
                "video_id", "2026-07-10T12:00:00Z", "test-oauth-token"
            )

        assert result["estimated_minutes_watched"] == 5000
        assert result["avg_view_duration"] == 120.5
        assert result["subscribers_gained"] == 25

    def test_no_oauth_token_returns_empty(self, mock_response):
        """Without OAuth token, returns empty dict."""
        from scripts.fetch_yt_analytics import fetch_analytics_api

        result = fetch_analytics_api(
            "video_id", "2026-07-10T12:00:00Z", None
        )

        assert result == {}

    def test_empty_rows_returns_empty(self, mock_response):
        """Empty rows in response returns empty dict (data not ready yet)."""
        from scripts.fetch_yt_analytics import fetch_analytics_api

        analytics_data = {"rows": []}

        with patch("scripts.fetch_yt_analytics.requests.get",
                   return_value=mock_response(json_data=analytics_data)):
            result = fetch_analytics_api(
                "video_id", "2026-07-10T12:00:00Z", "test-token"
            )

        assert result == {}

    def test_403_error_returns_empty(self, mock_response):
        """403 (API not enabled) returns empty dict, doesn't crash."""
        from scripts.fetch_yt_analytics import fetch_analytics_api

        with patch("scripts.fetch_yt_analytics.requests.get",
                   return_value=mock_response(status=403, raise_error=True)):
            result = fetch_analytics_api(
                "video_id", "2026-07-10T12:00:00Z", "test-token"
            )

        assert result == {}

    def test_generic_http_error_returns_empty(self, mock_response):
        """5xx errors return empty dict, don't crash."""
        from scripts.fetch_yt_analytics import fetch_analytics_api

        with patch("scripts.fetch_yt_analytics.requests.get",
                   return_value=mock_response(status=500, raise_error=True)):
            result = fetch_analytics_api(
                "video_id", "2026-07-10T12:00:00Z", "test-token"
            )

        assert result == {}


# ── OAuth Token (get_oauth_token) ────────────────────────────────────


class TestGetOAuthToken:
    """Tests for get_oauth_token()."""

    def test_no_token_file_returns_none(self, monkeypatch):
        """If TOKEN_PATH doesn't exist, returns None."""
        monkeypatch.setattr("scripts.fetch_yt_analytics.TOKEN_PATH",
                            "/tmp/nonexistent_token.json")
        from scripts.fetch_yt_analytics import get_oauth_token

        assert get_oauth_token() is None

    def test_token_file_loaded(self, monkeypatch, tmp_path):
        """Valid token file loads token string."""
        token_path = tmp_path / "yt-token.json"
        token_path.write_text(json.dumps({
            "token": "ya29.valid-token",
            "refresh_token": "1//refresh-token",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "test-client-id",
            "client_secret": "test-secret",
            "scopes": ["https://www.googleapis.com/auth/yt-analytics.readonly"],
        }))
        monkeypatch.setattr("scripts.fetch_yt_analytics.TOKEN_PATH", str(token_path))

        from scripts.fetch_yt_analytics import get_oauth_token

        token = get_oauth_token()
        assert token == "ya29.valid-token"

    def test_malformed_token_file_returns_none(self, monkeypatch, tmp_path):
        """Invalid JSON in token file returns None."""
        token_path = tmp_path / "yt-token.json"
        token_path.write_text("not-json")
        monkeypatch.setattr("scripts.fetch_yt_analytics.TOKEN_PATH", str(token_path))

        from scripts.fetch_yt_analytics import get_oauth_token

        # json.JSONDecodeError is caught by the except clause
        token = get_oauth_token()
        assert token is None


# ── Main Integration ─────────────────────────────────────────────────


class TestMain:
    """Tests for main() orchestration."""

    def test_video_not_found_exits(self, mock_response):
        """When Data API returns empty items, main sys.exits(1)."""
        api_data = {"items": []}

        with (
            patch("scripts.fetch_yt_analytics.requests.get",
                  return_value=mock_response(json_data=api_data)),
            patch("scripts.fetch_yt_analytics.load_env"),
            patch("scripts.fetch_yt_analytics.get_oauth_token",
                  return_value=None),
            patch("scripts.fetch_yt_analytics.sys.argv",
                  ["fetch-yt-analytics.py", "--video-id", "nonexistent"]),
            pytest.raises(SystemExit) as exc_info,
        ):
            from scripts.fetch_yt_analytics import main
            main()

        assert exc_info.value.code == 1


# ── Environment Loading ──────────────────────────────────────────────


def test_load_env_skips_missing_file(monkeypatch):
    """load_env doesn't crash when .env doesn't exist."""
    import pathlib
    monkeypatch.setattr("scripts.fetch_yt_analytics.ENV_PATH",
                        pathlib.Path("/tmp/nonexistent/.env"))
    from scripts.fetch_yt_analytics import load_env
    load_env()  # should not raise
