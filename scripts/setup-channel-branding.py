#!/usr/bin/env python3
"""
YouTube channel branding for CreatorForge Phase 5.
Sets channel description, tags, country, banner, watermark, and default settings.
Token must already exist (run setup-yt-oauth.py --channel Name first).

Usage:
  python scripts/setup-channel-branding.py --channel MyChannel
  python scripts/setup-channel-branding.py --channel MyChannel --banner path/to/banner.jpg
  python scripts/setup-channel-branding.py --channel MyChannel --watermark path/to/watermark.png
"""

import argparse
import json
import mimetypes
import sys
from pathlib import Path

try:
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload

    from agent_core.publishing.oauth import get_authenticated_service
except ImportError:
    print("Missing dependencies: pip install google-auth-oauthlib google-api-python-client")
    sys.exit(1)

from agent_core.core.validation import validate_or_raise

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))


def get_channel_config(channel: str) -> dict:
    config_path = PROJECT_ROOT / "channels" / channel / "channel_config.json"
    if config_path.exists():
        return json.loads(config_path.read_text())
    return {}


def save_channel_config(channel: str, config: dict):
    config_path = PROJECT_ROOT / "channels" / channel / "channel_config.json"
    config_path.write_text(json.dumps(config, indent=2))
    print("  ✓ channel_config.json updated")


def main():
    parser = argparse.ArgumentParser(description="Set YouTube channel branding")
    parser.add_argument("--channel", required=True, help="Channel name")
    parser.add_argument("--description", help="Channel description")
    parser.add_argument("--keywords", help="Channel tags/keywords (comma-separated)")
    parser.add_argument("--country", help="Channel country (ISO 3166-1 alpha-2)")
    parser.add_argument("--default-language", help="Default language (BCP-47, e.g., en)")
    parser.add_argument("--banner", help="Path to channel banner image")
    parser.add_argument("--watermark", help="Path to watermark image")
    parser.add_argument("--avatar", help="Path to channel avatar/profile picture (manual-only — no API endpoint)")
    parser.add_argument("--default-privacy", choices=["public", "unlisted", "private"],
                        help="Default upload privacy")
    parser.add_argument("--default-license", choices=["youtube", "creativeCommon"],
                        help="Default video license")
    parser.add_argument("--allow-embed", action=argparse.BooleanOptionalAction, default=None, help="Allow embedding by default")
    parser.add_argument("--allow-comments", action=argparse.BooleanOptionalAction, default=None, help="Allow comments by default")
    args = parser.parse_args()

    # Get authenticated YouTube API service
    youtube = get_authenticated_service(args.channel)

    # Get current channel info
    try:
        channels_response = youtube.channels().list(
            part="brandingSettings,id", mine=True
        ).execute()
    except HttpError as e:
        print(f"  ERROR: YouTube API request failed (HTTP {e.status_code}): {e.reason}")
        print(f"  Try: python scripts/setup-yt-oauth.py --channel {args.channel}")
        sys.exit(1)

    if not channels_response.get("items"):
        print("ERROR: No YouTube channel found for this account.")
        print("Create a YouTube channel manually first, then re-run.")
        sys.exit(1)

    channel_info = channels_response["items"][0]
    channel_id = channel_info["id"]
    branding = channel_info.get("brandingSettings", {}).get("channel", {})

    print(f"Channel ID: {channel_id}")
    print()

    # Build branding settings update
    update_needed = False
    updates = {
        "id": channel_id,
        "brandingSettings": {
            "channel": dict(branding),
        },
    }

    if args.description:
        updates["brandingSettings"]["channel"]["description"] = args.description
        update_needed = True
        print("  Description: set")

    if args.keywords:
        updates["brandingSettings"]["channel"]["keywords"] = args.keywords
        update_needed = True
        print(f"  Keywords: {args.keywords}")

    if args.country:
        updates["brandingSettings"]["channel"]["country"] = args.country
        update_needed = True
        print(f"  Country: {args.country}")

    if args.default_language:
        updates.setdefault("brandingSettings", {}).setdefault("channel", {})
        updates["brandingSettings"]["channel"]["defaultLanguage"] = args.default_language
        update_needed = True
        print(f"  Default language: {args.default_language}")

    if update_needed:
        try:
            youtube.channels().update(part="brandingSettings", body=updates).execute()
            print("  ✓ Channel branding settings saved")
        except HttpError as e:
            print(f"  ERROR: Failed to update branding settings (HTTP {e.status_code}): {e.reason}")
    else:
        print("  No branding text changes requested")

    # Load/create config early so all sections can populate it
    config = get_channel_config(args.channel)
    # Ensure required top-level sections exist for schema validation
    config.setdefault("channel_name", args.channel)
    config.setdefault("brand", {})
    config.setdefault("youtube", {})
    config.setdefault("production", {})
    config.setdefault("branding", {})

    # Upload banner
    if args.banner:
        banner_path = Path(args.banner)
        if not banner_path.exists():
            print(f"  ERROR: Banner file not found: {args.banner}")
        else:
            banner_mime = mimetypes.guess_type(str(banner_path))[0] or "image/jpeg"
            media = MediaFileUpload(str(banner_path), mimetype=banner_mime, resumable=True)
            try:
                banner_response = youtube.channelBanners().insert(
                    media_body=media, body={"channelId": channel_id}
                ).execute()
            except HttpError as e:
                print(f"  ERROR: Banner upload failed (HTTP {e.status_code}): {e.reason}")
                banner_response = {}
            banner_url = banner_response.get("url", "")
            if banner_url:
                print(f"  ✓ Banner uploaded: {banner_url}")
                # Apply banner to channel
                try:
                    youtube.channels().update(
                        part="brandingSettings",
                        body={
                            "id": channel_id,
                            "brandingSettings": {
                                "image": {"bannerExternalUrl": banner_url},
                            },
                        },
                    ).execute()
                    print("  ✓ Banner applied to channel")
                except HttpError as e:
                    print(f"  ERROR: Failed to apply banner to channel (HTTP {e.status_code}): {e.reason}")
            else:
                print("  ERROR: Banner upload returned no URL — banner was not applied")
            config["branding"]["banner_path"] = str(banner_path.resolve())

    # Set watermark
    if args.watermark:
        watermark_path = Path(args.watermark)
        if not watermark_path.exists():
            print(f"  ERROR: Watermark file not found: {args.watermark}")
        else:
            media = MediaFileUpload(str(watermark_path), mimetype="image/png", resumable=True)
            try:
                youtube.watermarks().set(
                    channelId=channel_id,
                    media_body=media,
                    body={
                        "timing": {
                            "type": "offsetFromStart",
                            "offsetMs": 5000,
                            "durationMs": 15000,
                        },
                    },
                ).execute()
                print("  ✓ Watermark set (appears 5s-20s into videos)")
            except HttpError as e:
                print(f"  ERROR: Watermark upload failed (HTTP {e.status_code}): {e.reason}")
            config["branding"]["watermark_path"] = str(watermark_path.resolve())

    # CHANNEL-03: Avatar/profile picture — manual-only
    # YouTube Data API v3 has no channel avatar upload endpoint.
    if args.avatar:
        avatar_path = Path(args.avatar)
        if avatar_path.exists():
            config["branding"]["avatar_path"] = str(avatar_path.resolve())
            print()
            print("  ⚠ Channel avatars can only be changed manually:")
            print("    1. Go to https://studio.youtube.com/")
            print("    2. Navigate to Customization → Branding")
            print("    3. Upload the image under 'Profile picture'")
            print()
            print(f"  Reference path stored: {avatar_path.resolve()}")
        else:
            print(f"  ERROR: Avatar file not found: {args.avatar}")
            print("  This is a manual-only step (no API endpoint).")

    # Persist remaining branding settings to channel_config.json
    if args.description:
        config["branding"]["description"] = args.description
    if args.keywords:
        config["branding"]["keywords"] = args.keywords
    if args.country:
        config["branding"]["country"] = args.country
    if args.default_language:
        config["branding"]["default_language"] = args.default_language
    config["branding"]["channel_id"] = channel_id

    # Default upload settings
    config.setdefault("defaults", {})
    if args.default_privacy:
        config["defaults"]["privacy"] = args.default_privacy
    if args.default_license:
        config["defaults"]["license"] = args.default_license
    if args.allow_embed is not None:
        config["defaults"]["embed"] = args.allow_embed
    if args.allow_comments is not None:
        config["defaults"]["comments"] = args.allow_comments

    # Validate against schema before saving
    try:
        validate_or_raise(config, "channel-config.schema.json")
    except ValueError as e:
        print(f"  ERROR: Config validation failed: {e}")
        print("  Config was NOT saved. Fix the issues above and re-run.")
        sys.exit(1)

    save_channel_config(args.channel, config)

    print()
    print(f"Done. Channel {args.channel} is branded and ready for publishing.")


if __name__ == "__main__":
    main()
