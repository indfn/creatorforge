"""Google OAuth handler for YouTube Data API and YouTube Analytics API access.

Manages the full OAuth token lifecycle: save initial token, load from disk,
auto-refresh on expiry, and build authenticated YouTube API service instances.

Public Functions:
    save_initial_token(channel, credentials) -> Path
        Persists a Credentials object to the per-channel token file.
    get_or_refresh_credentials(channel) -> Credentials
        Loads token from disk, refreshes if expired, returns valid Credentials.
    get_authenticated_service(channel) -> Resource
        Returns a live googleapiclient Resource authenticated for the channel.
    refresh_token_if_expired(channel) -> bool
        Refreshes token if expired. Returns True if valid, False if refresh failed.

Usage:
    from agent_core.publishing.oauth import get_authenticated_service
    youtube = get_authenticated_service("ChannelA")
"""

import json
import logging
from pathlib import Path

import google.auth.transport.requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

# ====== CONSTANTS ======

SCOPES = [
    # Channel management (Phase 5) — branding, default settings
    "https://www.googleapis.com/auth/youtube",
    # Video upload (Phase 6)
    "https://www.googleapis.com/auth/youtube.upload",
    # Analytics reading (Phase 7)
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]

TOKEN_FILENAME = "yt-oauth-token.json"


# ====== PRIVATE HELPERS ======


def _project_root() -> Path:
    """Resolve the project root directory.

    Returns the parent of agent_core/ — i.e. the repository root.
    Works regardless of the current working directory because it derives
    the path from this module's location on disk.
    """
    return Path(__file__).resolve().parent.parent.parent


def _token_path(channel: str) -> Path:
    """Resolve the per-channel OAuth token file path.

    Args:
        channel: Channel name (e.g. "ChannelA").

    Returns:
        Path to the token JSON file under channels/{channel}/.

    Raises:
        FileNotFoundError: If the channel directory does not exist.
    """
    channels_dir = _project_root() / "channels" / channel
    if not channels_dir.exists():
        raise FileNotFoundError(
            f"Channel directory not found: {channels_dir}. "
            f"Run /viral:onboard or create channels/{channel}/ first."
        )
    return channels_dir / TOKEN_FILENAME


def _load_token_data(channel: str) -> dict:
    """Load and parse the OAuth token JSON from disk.

    Args:
        channel: Channel name (e.g. "ChannelA").

    Returns:
        Parsed token dict with keys: token, refresh_token, token_uri,
        client_id, client_secret, scopes.

    Raises:
        FileNotFoundError: If the token file does not exist.
    """
    path = _token_path(channel)
    if not path.exists():
        raise FileNotFoundError(
            f"OAuth token not found at {path}. "
            f"Run: python scripts/setup-yt-oauth.py --channel {channel}"
        )
    return json.loads(path.read_text())


def _save_token(channel: str, creds: Credentials) -> Path:
    """Persist credentials to the per-channel token file.

    Args:
        channel: Channel name (e.g. "ChannelA").
        creds: The Credentials object to serialize.

    Returns:
        Path to the saved token file.
    """
    return save_initial_token(channel, creds)


# ====== PUBLIC API ======


def save_initial_token(channel: str, credentials: Credentials) -> Path:
    """Persist a Credentials object to the per-channel token file on disk.

    Serialises the credentials into the standard 6-field JSON format and
    writes it to ``channels/{channel}/yt-oauth-token.json``.  Creates the
    channel directory if it does not already exist.

    Args:
        channel: Channel name (e.g. "ChannelA").
        credentials: A google-auth Credentials object obtained from the
            OAuth flow (``run_local_server``) or from an existing token.

    Returns:
        Path to the saved token file.
    """
    token_data = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": list(credentials.scopes),
    }

    token_path = _project_root() / "channels" / channel / TOKEN_FILENAME
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(json.dumps(token_data, indent=2))
    return token_path


def get_or_refresh_credentials(channel: str) -> Credentials:
    """Load a channel's OAuth token from disk, refreshing it if expired.

    Builds a ``Credentials`` object from the stored token data.  If the
    token has expired and a ``refresh_token`` is available, it performs
    an automatic refresh via ``google.auth.transport.requests.Request()``
    and persists the updated token back to disk.

    Args:
        channel: Channel name (e.g. "ChannelA").

    Returns:
        A valid ``google.oauth2.credentials.Credentials`` instance.

    Raises:
        FileNotFoundError: If the channel directory or token file does
            not exist.
    """
    data = _load_token_data(channel)
    creds = Credentials(
        token=data["token"],
        refresh_token=data["refresh_token"],
        token_uri=data["token_uri"],
        client_id=data["client_id"],
        client_secret=data["client_secret"],
        scopes=data["scopes"],
    )

    if creds.expired and creds.refresh_token:
        creds.refresh(google.auth.transport.requests.Request())
        _save_token(channel, creds)
        logger.info("Refreshed expired OAuth token for channel: %s", channel)
    elif creds.expired and not creds.refresh_token:
        logger.warning(
            "Token for %s has no refresh_token. "
            "Re-run: python scripts/setup-yt-oauth.py --channel %s",
            channel,
            channel,
        )

    return creds


def get_authenticated_service(channel: str):
    """Build an authenticated YouTube API service for the given channel.

    Loads (and refreshes if needed) the OAuth credentials, then constructs
    a ``googleapiclient.discovery.Resource`` via ``build()``.

    ``static_discovery=False`` is set so that the discovery document is
    fetched live from the API rather than requiring a local cached copy.
    Without this flag the ``build()`` call raises
    ``UnknownApiNameOrVersion`` in environments without local discovery
    docs.

    Args:
        channel: Channel name (e.g. "ChannelA").

    Returns:
        An authenticated ``googleapiclient.discovery.Resource`` for the
        YouTube Data API v3.
    """
    creds = get_or_refresh_credentials(channel)
    return build("youtube", "v3", credentials=creds, static_discovery=False)


def refresh_token_if_expired(channel: str) -> bool:
    """Check whether the channel's OAuth token is still valid and refresh
    it if needed.

    Args:
        channel: Channel name (e.g. "ChannelA").

    Returns:
        ``True`` if the token is valid (either already fresh or
        successfully refreshed), ``False`` if the token is expired and
        cannot be refreshed (e.g. because there is no refresh_token).
    """
    data = _load_token_data(channel)
    creds = Credentials(
        token=data["token"],
        refresh_token=data["refresh_token"],
        token_uri=data["token_uri"],
        client_id=data["client_id"],
        client_secret=data["client_secret"],
        scopes=data["scopes"],
    )

    if not creds.expired:
        return True

    if creds.refresh_token:
        creds.refresh(google.auth.transport.requests.Request())
        _save_token(channel, creds)
        logger.info("Refreshed expired OAuth token for channel: %s", channel)
        return True

    logger.warning(
        "Token for %s has no refresh_token. "
        "Re-run: python scripts/setup-yt-oauth.py --channel %s",
        channel,
        channel,
    )
    return False
