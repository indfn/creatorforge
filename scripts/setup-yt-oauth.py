#!/usr/bin/env python3
"""
YouTube OAuth setup for the CreatorForge publishing project (Project B).
Authorizes channel management (branding), video upload, and analytics reading.
Token is saved per-channel for isolated publishing credentials.

Prerequisites:
  1. Create an OAuth 2.0 project in Google Cloud Console (the "publishing" project)
  2. Enable YouTube Data API v3 + YouTube Analytics API
  3. Configure the OAuth consent screen (verify yourself if in testing mode)
  4. Create OAuth 2.0 Desktop App credentials
  5. Download client_secret.json to scripts/client_secret.json
  6. Your YouTube channel must already exist (created manually)

This is separate from the API-key-only scraping project (Project A).
See .planning/ROADMAP.md Phase 5-6 for dual-credential architecture.

Usage:
  python scripts/setup-yt-oauth.py --channel MyChannel
"""

import argparse
import sys
from pathlib import Path

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:
    print("Missing dependency: pip install google-auth-oauthlib")
    sys.exit(1)

from agent_core.publishing.oauth import SCOPES, save_initial_token

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
CLIENT_SECRET = SCRIPT_DIR / "client_secret.json"


def main():
    parser = argparse.ArgumentParser(description="YouTube OAuth for CreatorForge")
    parser.add_argument("--channel", required=True, help="Channel name (e.g., MyChannel)")
    args = parser.parse_args()

    channel = args.channel
    channels_dir = PROJECT_ROOT / "channels" / channel

    if not channels_dir.exists():
        print(f"ERROR: Channel directory not found: {channels_dir}")
        print(f"Run /viral:onboard or create channels/{channel}/ first.")
        sys.exit(1)

    if not CLIENT_SECRET.exists():
        print(f"ERROR: {CLIENT_SECRET} not found.")
        print()
        print("To set up YouTube OAuth:")
        print("  1. Go to https://console.cloud.google.com/apis/credentials")
        print("  2. Create OAuth 2.0 Client ID (Desktop App)")
        print("  3. Download the JSON and save as: scripts/client_secret.json")
        sys.exit(1)

    print(f"Starting YouTube OAuth flow for channel: {channel}")
    print("Scopes: channel management + video upload + analytics read")
    print("A browser window will open for authorization.\n")

    flow = InstalledAppFlow.from_client_secrets_file(
        str(CLIENT_SECRET), scopes=SCOPES
    )
    credentials = flow.run_local_server(port=8080)

    token_path = save_initial_token(channel, credentials)
    print(f"\nToken saved to {token_path}")
    print("YouTube channel management + publishing + analytics are ready.")


if __name__ == "__main__":
    main()
