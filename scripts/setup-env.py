#!/usr/bin/env python3
"""
Interactive .env configuration walkthrough.

Opens signup URLs in your browser for each API key group,
prompts you to paste the key, and saves to .env.

Usage:
    python scripts/setup-env.py          # full walkthrough
    python scripts/setup-env.py --check  # only show missing keys
"""

import argparse
import os
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
ENV_PATH = PROJECT_ROOT / ".env"
ENV_EXAMPLE_PATH = PROJECT_ROOT / ".env.example"

DIM = "\033[2m"
GREEN = "\033[1;32m"
CYAN = "\033[1;36m"
YELLOW = "\033[1;33m"
RESET = "\033[0m"


def dim(t): return f"{DIM}{t}{RESET}"
def green(t): return f"{GREEN}{t}{RESET}"
def cyan(t): return f"{CYAN}{t}{RESET}"
def yellow(t): return f"{YELLOW}{t}{RESET}"


KEY_GROUPS = [
    {
        "title": "LLM Provider — Content Analysis",
        "keys": ["LLM_API_KEY"],
        "provider": "OpenAI",
        "url": "https://platform.openai.com/api-keys",
        "note": "Paid API (usage costs). Required for extracting content skeletons.",
    },
    {
        "title": "Transcription — Groq Whisper (Free)",
        "keys": ["GROQ_API_KEY"],
        "provider": "Groq",
        "url": "https://console.groq.com/keys",
        "note": "Free tier, rate-limited. Used for transcribing competitor videos.",
    },
    {
        "title": "YouTube Data API",
        "keys": ["YOUTUBE_DATA_API_KEY"],
        "provider": "Google Cloud",
        "url": "https://console.cloud.google.com/apis/credentials",
        "note": "Free tier (10K quota/day). Enables competitor discovery & analytics.",
    },
    {
        "title": "Instagram Graph API",
        "keys": ["INSTAGRAM_ACCESS_TOKEN", "INSTAGRAM_BUSINESS_ACCOUNT_ID", "INSTAGRAM_APP_ID", "INSTAGRAM_APP_SECRET"],
        "provider": "Meta for Developers",
        "url": "https://developers.facebook.com/apps/",
        "note": "Run scripts/setup-ig-token.py after creating a Facebook app.",
        "skip_if": lambda env: env.get("INSTAGRAM_BUSINESS_ACCOUNT_ID", "").strip() != "",
        "skip_message": "Instagram already configured (has INSTAGRAM_BUSINESS_ACCOUNT_ID)",
    },
    {
        "title": "TTS — Text-to-Speech",
        "keys": ["GEMINI_API_KEY"],
        "provider": "Google AI Studio",
        "url": "https://aistudio.google.com/apikey",
        "note": "Free tier (60 req/min). Used for voiceover generation.",
    },
    {
        "title": "Stock Media — Pexels (B-roll footage)",
        "keys": ["PEXELS_API_KEY"],
        "provider": "Pexels",
        "url": "https://www.pexels.com/api/",
        "note": "Free (200 req/hr). Primary source for video B-roll.",
    },
    {
        "title": "Stock Media — Pixabay (Fallback B-roll)",
        "keys": ["PIXABAY_API_KEY"],
        "provider": "Pixabay",
        "url": "https://pixabay.com/api/docs/",
        "note": "Free (unlimited). Fallback when Pexels has no results.",
    },
    {
        "title": "SFX — Freesound (Sound Effects)",
        "keys": ["FREESOUND_API_KEY"],
        "provider": "Freesound",
        "url": "https://freesound.org/apiv2/apply/",
        "note": "Free (60 req/min). Preview URLs only, non-commercial.",
    },
]


def load_env():
    env = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip().strip("\"'")
    return env


def save_env(env):
    lines = []
    written = set()
    if ENV_EXAMPLE_PATH.exists():
        for line in ENV_EXAMPLE_PATH.read_text().splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                lines.append(line)
                continue
            if "=" in stripped:
                key = stripped.split("=", 1)[0].strip()
                if key in env:
                    lines.append(f"{key}={env[key]}")
                    written.add(key)
                else:
                    lines.append(line)
            else:
                lines.append(line)
        for key, val in env.items():
            if key not in written:
                lines.append(f"{key}={val}")
    else:
        for key, val in env.items():
            lines.append(f"{key}={val}")
    ENV_PATH.write_text("\n".join(lines) + "\n")


def open_url(url):
    webbrowser.open(url)
    print(f"  Opened: {dim(url)}")


def prompt_key(label, provider, existing=""):
    display = f"{label} ({provider})"
    if existing:
        hint = existing[:8] + "..." if len(existing) > 8 else existing
        print(f"  Current: {green(hint)}")
    val = input(f"  Enter {label} [{dim('enter=skip')}]: ").strip()
    return val or existing


def main():
    parser = argparse.ArgumentParser(description="Interactive .env configuration")
    parser.add_argument("--check", action="store_true", help="Only show missing keys, don't prompt")
    args = parser.parse_args()

    print()
    print("  CreatorForge — API Key Setup")
    print(f"  {dim('Will walk through each API key group, open signup URLs,')}")
    print(f"  {dim('and save your keys to .env.')}")
    print()

    # Ensure .env exists
    if not ENV_PATH.exists():
        if ENV_EXAMPLE_PATH.exists():
            shutil.copy(ENV_EXAMPLE_PATH, ENV_PATH)
            print(f"  Created .env from {dim('.env.example')}")
        else:
            ENV_PATH.write_text("# CreatorForge Environment\n")
            print(f"  Created empty {dim('.env')}")

    env = load_env()

    if args.check:
        print(f"  {cyan('Missing keys:')}")
        print()
        missing = 0
        for group in KEY_GROUPS:
            group_missing = [k for k in group["keys"] if not env.get(k)]
            if group_missing:
                missing += len(group_missing)
                print(f"  {yellow('✗')} {group['title']}")
                for k in group_missing:
                    print(f"      {k}  {dim(group['url'])}")
        if missing == 0:
            print(f"  {green('All API keys configured!')}")
        print()
        return

    for group in KEY_GROUPS:
        skip_fn = group.get("skip_if")
        if skip_fn and skip_fn(env):
            print(f"  {green('✓')} {group['title']} — {group['skip_message']}")
            print()
            continue

        print(f"  {cyan(group['title'])}")
        print(f"  {dim(group['note'])}")
        print()

        all_set = all(env.get(k) for k in group["keys"])
        if all_set:
            print(f"  {green('✓')} All keys present")
            refresh = input(f"  Reconfigure? [{dim('y/N')}]: ").strip().lower()
            if refresh != "y":
                print()
                continue

        if not all_set:
            open_url(group["url"])
            print()

        for key in group["keys"]:
            env[key] = prompt_key(key, group["provider"], env.get(key, ""))

        save_env(env)
        print(f"  {green('✓')} {group['title']} saved")
        print()

    print(f"  {green('All keys saved to .env!')}")
    print(f"  Run {cyan('creatorforge doctor')} to verify.")
    print()


if __name__ == "__main__":
    main()
