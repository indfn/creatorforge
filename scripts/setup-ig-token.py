#!/usr/bin/env python3
"""
Instagram Graph API — One-time token setup.

Gets a long-lived Instagram access token and Business Account ID,
saves all four Instagram variables to .env.

Usage:
    python scripts/setup-ig-token.py              # auto — starts a local server
    python scripts/setup-ig-token.py --manual     # manual copy-paste (no server)

Prerequisites:
  1. Instagram account must be Business or Creator (not Personal)
  2. Instagram account linked to a Facebook Page
  3. Facebook Developer App created at developers.facebook.com
  4. App has instagram_basic + instagram_manage_insights (requires App Review)
"""

import argparse
import json
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

try:
    import requests
except ImportError:
    print("Missing dependency: pip install requests")
    sys.exit(1)

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
ENV_PATH = PROJECT_ROOT / ".env"

GRAPH_API_VERSION = "v21.0"
BASE_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"
LOCAL_PORT = 8199
DIM = "\033[2m"
GREEN = "\033[1;32m"
RESET = "\033[0m"


def dim(t): return f"{DIM}{t}{RESET}"
def green(t): return f"{GREEN}{t}{RESET}"


class RedirectHandler(BaseHTTPRequestHandler):
    """Catches the OAuth redirect and extracts the authorization code."""

    auth_code = None

    def do_GET(self):
        params = parse_qs(urlparse(self.path).query)
        code = params.get("code", [None])[0]

        if code:
            RedirectHandler.auth_code = code
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                "<html><body><h2>Authorization successful!</h2>"
                "<p>You can close this tab now.</p>"
                "<script>window.close()</script></body></html>".encode()
            )
        else:
            error = params.get("error", ["unknown"])[0]
            self.send_response(400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                f"<html><body><h2>Authorization failed: {error}</h2>"
                f"<p>Close this tab and try again.</p></body></html>".encode()
            )

    def log_message(self, fmt, *args):
        pass  # suppress server logs


def update_env(key, value):
    lines = []
    found = False
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            if line.strip().startswith(f"{key}="):
                lines.append(f"{key}={value}")
                found = True
            else:
                lines.append(line)
    if not found:
        lines.append("")
        lines.append(f"{key}={value}")
    ENV_PATH.write_text("\n".join(lines) + "\n")


def exchange_code(code, app_id, app_secret):
    resp = requests.get(
        f"{BASE_URL}/oauth/access_token",
        params={"client_id": app_id, "client_secret": app_secret,
                "redirect_uri": f"http://localhost:{LOCAL_PORT}/", "code": code},
        timeout=15,
    )
    if resp.status_code != 200:
        print(f"ERROR: Token exchange failed: {resp.text}")
        sys.exit(1)
    return resp.json()["access_token"]


def exchange_long_token(short_token, app_id, app_secret):
    resp = requests.get(
        f"{BASE_URL}/oauth/access_token",
        params={"grant_type": "fb_exchange_token", "client_id": app_id,
                "client_secret": app_secret, "fb_exchange_token": short_token},
        timeout=15,
    )
    if resp.status_code != 200:
        print(f"ERROR: Long-lived token exchange failed: {resp.text}")
        sys.exit(1)
    return resp.json()["access_token"], resp.json().get("expires_in", 5184000)


def get_ig_business_account(long_token):
    resp = requests.get(
        f"{BASE_URL}/me/accounts",
        params={"access_token": long_token, "fields": "id,name,instagram_business_account"},
        timeout=15,
    )
    if resp.status_code != 200:
        print(f"ERROR: Could not fetch Pages: {resp.text}")
        sys.exit(1)
    pages = resp.json().get("data", [])
    for page in pages:
        ig = page.get("instagram_business_account")
        if ig:
            print(f"  Found: {page['name']} → Instagram ID: {ig['id']}")
            return ig["id"]
    print("ERROR: No Instagram Business Account found.")
    print("Make sure your Instagram is linked to a Facebook Page.")
    sys.exit(1)


def finish_flow(code, app_id, app_secret):
    print("\nExchanging code for access token...")
    short_token = exchange_code(code, app_id, app_secret)

    print("Exchanging for long-lived token (60 days)...")
    long_token, expires_in = exchange_long_token(short_token, app_id, app_secret)
    days = expires_in // 86400

    print("Finding Instagram Business Account...")
    ig_account_id = get_ig_business_account(long_token)

    update_env("INSTAGRAM_ACCESS_TOKEN", long_token)
    update_env("INSTAGRAM_BUSINESS_ACCOUNT_ID", ig_account_id)
    update_env("INSTAGRAM_APP_ID", app_id)
    update_env("INSTAGRAM_APP_SECRET", app_secret)

    print()
    print("=" * 50)
    print("Setup complete!")
    print(f"  Token expires in ~{days} days")
    print(f"  Instagram Account ID: {ig_account_id}")
    print(f"  Saved to: {ENV_PATH}")
    print()
    print("Auto-refresh: run scripts/refresh-ig-token.sh before expiry")
    print("=" * 50)


def main():
    parser = argparse.ArgumentParser(description="Instagram Graph API token setup")
    parser.add_argument("--manual", action="store_true", help="Manual copy-paste mode (no local server)")
    args = parser.parse_args()

    print("=" * 50)
    print("Instagram Graph API — Token Setup")
    print("=" * 50)
    print()

    app_id = input("Facebook App ID: ").strip()
    app_secret = input("Facebook App Secret: ").strip()
    if not app_id or not app_secret:
        print("ERROR: App ID and Secret are required.")
        sys.exit(1)

    redirect_uri = f"http://localhost:{LOCAL_PORT}/"

    auth_url = (
        f"https://www.facebook.com/{GRAPH_API_VERSION}/dialog/oauth"
        f"?client_id={app_id}"
        f"&redirect_uri={redirect_uri}"
        f"&scope=instagram_basic,instagram_manage_insights,pages_show_list,pages_read_engagement"
        f"&response_type=code"
    )

    if args.manual:
        print()
        print("Step 1: Open this URL in your browser and authorize:")
        print()
        print(f"  {auth_url}")
        print()
        print("After authorization, you'll be redirected.")
        print("Copy the FULL redirect URL from the address bar and paste it below.")
        redirect_url = input("Paste the redirect URL here: ").strip()
        if "code=" not in redirect_url:
            print("ERROR: Could not find authorization code in URL.")
            sys.exit(1)
        code = redirect_url.split("code=")[1].split("&")[0].split("#")[0]
    else:
        server = HTTPServer(("0.0.0.0", LOCAL_PORT), RedirectHandler)
        server.timeout = 120
        print()
        print(f"Starting local server on port {LOCAL_PORT}...")
        print(f"Opening browser for Facebook authorization...")
        print()
        print(f"  {auth_url}")
        print()

        import webbrowser
        webbrowser.open(auth_url)

        print("Waiting for redirect... (server will shut down automatically)")
        print(f"  {dim('If the browser does not open, copy the URL above manually.')}")
        print(f"  {dim('Timeout: 120 seconds')}")
        print()

        while RedirectHandler.auth_code is None:
            server.handle_request()

        code = RedirectHandler.auth_code

    finish_flow(code, app_id, app_secret)


if __name__ == "__main__":
    main()
