"""Mock-based tests for scripts/fetch-ig-insights.py.

Tests cover: media field parsing, reel vs image insights, engagement rate
calculation, follower delta, error handling, and main() orchestration.
"""

from unittest.mock import Mock, patch

import pytest


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    """Prevent tests from touching real .env or env vars."""
    monkeypatch.delenv("INSTAGRAM_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", raising=False)
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "test-ig-token")
    monkeypatch.setenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "test-account-id")


@pytest.fixture
def mock_response():
    """Build a mock requests.Response."""
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


# ── Media fields response helper ─────────────────────────────────────

def _media_fields_response(media_id="test_media_123",
                           caption="Test post caption",
                           timestamp="2026-07-10T14:30:00+00:00",
                           media_type="VIDEO",
                           like_count=100,
                           comments_count=20):
    """Build a standard Instagram media fields API response."""
    return {
        "id": media_id,
        "caption": caption,
        "timestamp": timestamp,
        "media_type": media_type,
        "like_count": like_count,
        "comments_count": comments_count,
        "permalink": f"https://instagram.com/p/{media_id}/",
    }


# ── Tests ────────────────────────────────────────────────────────────


class TestGetMediaInsights:
    """Tests for get_media_insights()."""

    def test_video_media_basic_fields(self, mock_response):
        """VIDEO media returns correct basic fields from media API."""
        from scripts.fetch_ig_insights import get_media_insights

        media_data = _media_fields_response()

        with patch("scripts.fetch_ig_insights.requests.get",
                   return_value=mock_response(json_data=media_data)):
            result = get_media_insights("test_media_123", "test-token")

        assert result["media_id"] == "test_media_123"
        assert result["caption"] == "Test post caption"
        assert result["published_at"] == "2026-07-10T14:30:00+00:00"
        assert result["media_type"] == "VIDEO"
        assert result["metrics"]["likes"] == 100
        assert result["metrics"]["comments"] == 20

    def test_video_media_insights_metrics(self, mock_response):
        """VIDEO media fetches insight metrics (reach, saved, shares, plays, total_interactions)."""
        from scripts.fetch_ig_insights import get_media_insights

        # Two sequential calls: media fields then insights
        media_data = _media_fields_response(media_type="VIDEO")
        insights_data = {
            "data": [
                {"name": "reach", "values": [{"value": 5000}]},
                {"name": "saved", "values": [{"value": 200}]},
                {"name": "shares", "values": [{"value": 150}]},
                {"name": "plays", "values": [{"value": 8000}]},
                {"name": "total_interactions", "values": [{"value": 300}]},
            ]
        }

        # First call returns media fields, second returns insights
        mock_responses = [
            mock_response(json_data=media_data),
            mock_response(json_data=insights_data),
        ]

        with patch("scripts.fetch_ig_insights.requests.get",
                   side_effect=mock_responses):
            result = get_media_insights("test_media_123", "test-token")

        assert result["metrics"]["reach"] == 5000
        assert result["metrics"]["saves"] == 200
        assert result["metrics"]["shares"] == 150
        assert result["metrics"]["views"] == 8000  # plays mapped to views
        assert result["metrics"]["total_interactions"] == 300

    def test_video_engagement_rate(self, mock_response):
        """Engagement rate = (likes+comments+shares+saves) / views * 100."""
        from scripts.fetch_ig_insights import get_media_insights

        media_data = _media_fields_response(
            media_type="VIDEO", like_count=200, comments_count=50
        )
        insights_data = {
            "data": [
                {"name": "reach", "values": [{"value": 10000}]},
                {"name": "saved", "values": [{"value": 300}]},
                {"name": "shares", "values": [{"value": 100}]},
                {"name": "plays", "values": [{"value": 10000}]},
            ]
        }

        mock_responses = [
            mock_response(json_data=media_data),
            mock_response(json_data=insights_data),
        ]

        with patch("scripts.fetch_ig_insights.requests.get",
                   side_effect=mock_responses):
            result = get_media_insights("test_media_123", "test-token")

        # (200 + 50 + 100 + 300) / 10000 * 100 = 6.5
        assert result["metrics"]["engagement_rate"] == 6.5

    def test_image_media_no_plays(self, mock_response):
        """IMAGE media gets reach, saved, shares but NOT plays/views."""
        from scripts.fetch_ig_insights import get_media_insights

        media_data = _media_fields_response(
            media_type="IMAGE", like_count=50, comments_count=10
        )
        insights_data = {
            "data": [
                {"name": "reach", "values": [{"value": 3000}]},
                {"name": "saved", "values": [{"value": 100}]},
                {"name": "shares", "values": [{"value": 50}]},
            ]
        }

        mock_responses = [
            mock_response(json_data=media_data),
            mock_response(json_data=insights_data),
        ]

        with patch("scripts.fetch_ig_insights.requests.get",
                   side_effect=mock_responses):
            result = get_media_insights("image_123", "test-token")

        assert "reach" in result["metrics"]
        assert "saves" in result["metrics"]
        assert "shares" in result["metrics"]
        # IMAGE media doesn't use 'plays' metric, so views should not be set
        assert result["metrics"].get("views") is None

    def test_image_engagement_rate_uses_reach(self, mock_response):
        """IMAGE engagement uses reach as denominator (no views metric)."""
        from scripts.fetch_ig_insights import get_media_insights

        media_data = _media_fields_response(
            media_type="IMAGE", like_count=100, comments_count=20
        )
        insights_data = {
            "data": [
                {"name": "reach", "values": [{"value": 5000}]},
                {"name": "saved", "values": [{"value": 150}]},
                {"name": "shares", "values": [{"value": 75}]},
            ]
        }

        mock_responses = [
            mock_response(json_data=media_data),
            mock_response(json_data=insights_data),
        ]

        with patch("scripts.fetch_ig_insights.requests.get",
                   side_effect=mock_responses):
            result = get_media_insights("image_123", "test-token")

        # (100 + 20 + 75 + 150) / 5000 * 100 = 6.9
        assert result["metrics"]["engagement_rate"] == 6.9

    def test_insights_400_error_does_not_crash(self, mock_response):
        """400 error from insights API is silently handled (some metrics unavailable for media type)."""
        from scripts.fetch_ig_insights import get_media_insights

        media_data = _media_fields_response(media_type="VIDEO")

        mock_responses = [
            mock_response(json_data=media_data),
            mock_response(status=400, raise_error=True),
        ]

        with patch("scripts.fetch_ig_insights.requests.get",
                   side_effect=mock_responses):
            # Should NOT raise — 400 is caught in the VIDEO branch
            result = get_media_insights("test_media_123", "test-token")

        assert result["media_id"] == "test_media_123"
        # Insights metrics should just not be present
        assert result["metrics"].get("reach") is None

    def test_generic_insights_error_does_not_crash(self, mock_response):
        """Generic HTTP errors from insights are caught without crashing."""
        from scripts.fetch_ig_insights import get_media_insights

        media_data = _media_fields_response(media_type="VIDEO")

        mock_responses = [
            mock_response(json_data=media_data),
            mock_response(status=500, raise_error=True),
        ]

        with patch("scripts.fetch_ig_insights.requests.get",
                   side_effect=mock_responses):
            result = get_media_insights("test_media_123", "test-token")

        assert result["media_id"] == "test_media_123"
        # The except clause catches HTTPError (via e.response.status_code) or generic Exception
        assert result["metrics"].get("views") is None

    def test_media_fields_timeout_propagates(self, mock_response):
        """Timeout from media fields request propagates (no try/except around first request)."""
        from scripts.fetch_ig_insights import get_media_insights
        from requests.exceptions import Timeout

        with patch("scripts.fetch_ig_insights.requests.get",
                   side_effect=Timeout("Connection timed out")):
            with pytest.raises(Timeout):
                get_media_insights("test_media_123", "test-token")

    def test_media_fields_connection_error_propagates(self, mock_response):
        """ConnectionError from media fields request propagates."""
        from scripts.fetch_ig_insights import get_media_insights
        from requests.exceptions import ConnectionError

        with patch("scripts.fetch_ig_insights.requests.get",
                   side_effect=ConnectionError("Connection refused")):
            with pytest.raises(ConnectionError):
                get_media_insights("test_media_123", "test-token")

    def test_insights_timeout_propagates(self, mock_response):
        """Timeout from insights request propagates (except only catches HTTPError)."""
        from scripts.fetch_ig_insights import get_media_insights
        from requests.exceptions import Timeout

        media_data = _media_fields_response(media_type="VIDEO")

        mock_responses = [
            mock_response(json_data=media_data),
            Timeout("Connection timed out"),
        ]

        with patch("scripts.fetch_ig_insights.requests.get",
                   side_effect=mock_responses):
            with pytest.raises(Timeout):
                get_media_insights("test_media_123", "test-token")

    def test_insights_connection_error_propagates(self, mock_response):
        """ConnectionError from insights request propagates."""
        from scripts.fetch_ig_insights import get_media_insights
        from requests.exceptions import ConnectionError

        media_data = _media_fields_response(media_type="VIDEO")

        mock_responses = [
            mock_response(json_data=media_data),
            ConnectionError("Connection refused"),
        ]

        with patch("scripts.fetch_ig_insights.requests.get",
                   side_effect=mock_responses):
            with pytest.raises(ConnectionError):
                get_media_insights("test_media_123", "test-token")


class TestGetFollowerDelta:
    """Tests for get_follower_delta()."""

    def test_positive_delta(self, mock_response):
        """Returns positive follower count change."""
        from scripts.fetch_ig_insights import get_follower_delta

        follower_data = {
            "data": [{
                "values": [
                    {"value": 50000},
                    {"value": 50150},
                ]
            }]
        }

        with patch("scripts.fetch_ig_insights.requests.get",
                   return_value=mock_response(json_data=follower_data)):
            delta = get_follower_delta(
                "account_123", "test-token", "2026-07-10T14:30:00+00:00"
            )

        assert delta == 150  # 50150 - 50000

    def test_single_value_returns_none(self, mock_response):
        """Only one data point — can't compute delta."""
        from scripts.fetch_ig_insights import get_follower_delta

        follower_data = {
            "data": [{
                "values": [
                    {"value": 50000},
                ]
            }]
        }

        with patch("scripts.fetch_ig_insights.requests.get",
                   return_value=mock_response(json_data=follower_data)):
            delta = get_follower_delta(
                "account_123", "test-token", "2026-07-10T14:30:00+00:00"
            )

        assert delta is None

    def test_negative_delta_clamped_to_zero(self, mock_response):
        """Negative follower change returns 0 (don't report negative attributed growth)."""
        from scripts.fetch_ig_insights import get_follower_delta

        follower_data = {
            "data": [{
                "values": [
                    {"value": 50000},
                    {"value": 49800},
                ]
            }]
        }

        with patch("scripts.fetch_ig_insights.requests.get",
                   return_value=mock_response(json_data=follower_data)):
            delta = get_follower_delta(
                "account_123", "test-token", "2026-07-10T14:30:00+00:00"
            )

        assert delta == 0  # max(0, -200)

    def test_missing_data_returns_none(self, mock_response):
        """Empty data array returns None."""
        from scripts.fetch_ig_insights import get_follower_delta

        follower_data = {"data": []}

        with patch("scripts.fetch_ig_insights.requests.get",
                   return_value=mock_response(json_data=follower_data)):
            delta = get_follower_delta(
                "account_123", "test-token", "2026-07-10T14:30:00+00:00"
            )

        assert delta is None

    def test_api_error_returns_none(self, mock_response):
        """API errors return None without crashing."""
        from scripts.fetch_ig_insights import get_follower_delta

        with patch("scripts.fetch_ig_insights.requests.get",
                   return_value=mock_response(status=500, raise_error=True)):
            delta = get_follower_delta(
                "account_123", "test-token", "2026-07-10T14:30:00+00:00"
            )

        assert delta is None


class TestGetRecentMedia:
    """Tests for get_recent_media()."""

    def test_returns_media_list(self, mock_response):
        """Returns list of media items from paginated response."""
        from scripts.fetch_ig_insights import get_recent_media

        media_data = {
            "data": [
                {"id": "media_1", "caption": "Post 1", "timestamp": "2026-07-10T12:00:00Z", "media_type": "VIDEO"},
                {"id": "media_2", "caption": "Post 2", "timestamp": "2026-07-09T12:00:00Z", "media_type": "IMAGE"},
            ]
        }

        with patch("scripts.fetch_ig_insights.requests.get",
                   return_value=mock_response(json_data=media_data)):
            result = get_recent_media("account_123", "test-token", limit=2)

        assert len(result) == 2
        assert result[0]["id"] == "media_1"
        assert result[1]["media_type"] == "IMAGE"

    def test_empty_list(self, mock_response):
        """Account with no media returns empty list."""
        from scripts.fetch_ig_insights import get_recent_media

        with patch("scripts.fetch_ig_insights.requests.get",
                   return_value=mock_response(json_data={"data": []})):
            result = get_recent_media("account_123", "test-token", limit=5)

        assert result == []


class TestMain:
    """Tests for main() orchestration."""

    def test_missing_access_token_exits(self, monkeypatch):
        """Missing INSTAGRAM_ACCESS_TOKEN triggers sys.exit(1)."""
        monkeypatch.delenv("INSTAGRAM_ACCESS_TOKEN", raising=False)

        from scripts.fetch_ig_insights import main

        with (
            patch("scripts.fetch_ig_insights.sys.argv",
                  ["fetch-ig-insights.py", "--media-id", "test123"]),
            pytest.raises(SystemExit) as exc_info,
        ):
            main()

        assert exc_info.value.code == 1

    def test_missing_account_id_exits(self, monkeypatch):
        """Missing INSTAGRAM_BUSINESS_ACCOUNT_ID triggers sys.exit(1)."""
        monkeypatch.delenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", raising=False)

        from scripts.fetch_ig_insights import main

        with (
            patch("scripts.fetch_ig_insights.sys.argv",
                  ["fetch-ig-insights.py", "--media-id", "test123"]),
            pytest.raises(SystemExit) as exc_info,
        ):
            main()

        assert exc_info.value.code == 1

    def test_media_id_flow_completes(self, mock_response):
        """--media-id flow: fetches single post and returns list with one result."""
        from scripts.fetch_ig_insights import main

        media_data = _media_fields_response(media_type="VIDEO")
        insights_data = {
            "data": [
                {"name": "plays", "values": [{"value": 5000}]},
                {"name": "reach", "values": [{"value": 4000}]},
            ]
        }
        follower_data = {
            "data": [{
                "values": [
                    {"value": 100000},
                    {"value": 100050},
                ]
            }]
        }

        mock_responses = [
            mock_response(json_data=media_data),        # media fields
            mock_response(json_data=insights_data),      # insights
            mock_response(json_data=follower_data),      # follower delta
        ]

        with (
            patch("scripts.fetch_ig_insights.requests.get",
                  side_effect=mock_responses),
            patch("scripts.fetch_ig_insights.load_env"),
            patch("scripts.fetch_ig_insights.sys.argv",
                  ["fetch-ig-insights.py", "--media-id", "test_media_123"]),
        ):
            results = main()

        assert len(results) == 1
        assert results[0]["media_id"] == "test_media_123"
        assert results[0]["metrics"]["followers_gained_attributed"] == 50


class TestCaptionTruncation:
    """Caption is truncated to 100 chars."""

    def test_long_caption_truncated(self, mock_response):
        """Caption > 100 chars is truncated."""
        from scripts.fetch_ig_insights import get_media_insights

        long_caption = "A" * 200
        media_data = _media_fields_response(caption=long_caption, media_type="IMAGE")

        # For IMAGE, insights try the second endpoint which may 400
        mock_responses = [
            mock_response(json_data=media_data),
            mock_response(status=400, raise_error=True),
        ]

        with patch("scripts.fetch_ig_insights.requests.get",
                   side_effect=mock_responses):
            result = get_media_insights("test_media", "test-token")

        assert len(result["caption"]) == 100
        assert result["caption"] == "A" * 100


class TestEnvLoading:
    """Tests for load_env()."""

    def test_load_env_no_crash(self, monkeypatch):
        """load_env doesn't crash when .env doesn't exist."""
        import pathlib
        monkeypatch.setattr("scripts.fetch_ig_insights.ENV_PATH",
                            pathlib.Path("/tmp/nonexistent/.env"))
        from scripts.fetch_ig_insights import load_env
        load_env()  # should not raise
