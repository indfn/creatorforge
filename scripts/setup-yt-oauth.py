#!/usr/bin/env python3
"""
One-time YouTube OAuth setup for YouTube Data & Analytics APIs.
Opens browser for authorization, saves per-channel token to channels/{Name}/yt-oauth-token.json.

Prerequisites:
  1. Enable YouTube Data API v3 in Google Cloud Console
  2. Create OAuth 2.0 Desktop App credentials
  3. Download client_secret.json to scripts/client_secret.json

Usage:
  python scripts/setup-yt-oauth.py --channel MyChannel
"""

import argparse
import sys
from pathlib import Path

try:
    from google_auth_oauthlib.flow import InstalledAppFlow

    from agent_core.publishing.oauth import SCOPES, save_initial_token
except ImportError:
    print("Missing dependency: pip install google-auth-oauthlib")
    sys.exit(1)

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
CLIENT_SECRET = SCRIPT_DIR / "client_secret.json"


def main():
    parser = argparse.ArgumentParser(description="One-time YouTube OAuth setup")
    parser.add_argument("--channel", required=True, help="Channel name")
    args = parser.parse_args()

    if not CLIENT_SECRET.exists():
        print(f"ERROR: {CLIENT_SECRET} not found.")
        print()
        print("To set up YouTube OAuth:")
        print("  1. Go to https://console.cloud.google.com/apis/credentials")
        print("  2. Create OAuth 2.0 Client ID (Desktop App)")
        print("  3. Download the JSON and save as: scripts/client_secret.json")
        sys.exit(1)

    print("Starting YouTube OAuth flow...")
    print("A browser window will open for authorization.\n")

    flow = InstalledAppFlow.from_client_secrets_file(
        str(CLIENT_SECRET), scopes=SCOPES
    )
    credentials = flow.run_local_server(port=8080)

    saved_path = save_initial_token(args.channel, credentials)
    print(f"\nToken saved to {saved_path}")
    print("YouTube Analytics API is ready. Future pulls will use this token silently.")


if __name__ == "__main__":
    main()
