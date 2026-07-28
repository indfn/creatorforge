#!/usr/bin/env python3
"""
creatorforge doctor — Health check for your CreatorForge setup.

Scans .env keys, installed tools, credential encryption, OAuth tokens,
channel directories, and network connectivity. Exits non-zero if any
critical check fails.

Usage:
    python scripts/doctor.py          # full check
    python scripts/doctor.py --quiet  # only show failures
    python scripts/doctor.py --fix    # attempt auto-fix for common issues
"""

import argparse
import os
import shutil
import subprocess
import sys
import json
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"
INFO = "INFO"


def green(text):
    return f"\033[1;32m{text}\033[0m"


def red(text):
    return f"\033[1;31m{text}\033[0m"


def yellow(text):
    return f"\033[1;33m{text}\033[0m"


def dim(text):
    return f"\033[2m{text}\033[0m"


def cyan(text):
    return f"\033[1;36m{text}\033[0m"


def status_tag(result):
    return {"PASS": green("PASS"), "FAIL": red("FAIL"), "WARN": yellow("WARN"), "INFO": cyan("INFO")}[result]


checks_run = 0
checks_failed = 0


class Check:
    def __init__(self, name, result=PASS, detail=""):
        global checks_run, checks_failed
        checks_run += 1
        if result == FAIL:
            checks_failed += 1
        self.name = name
        self.result = result
        self.detail = detail

    def __repr__(self):
        return f"  [{status_tag(self.result)}] {self.name}" + (f"  {dim(self.detail)}" if self.detail else "")


def run(cmd, timeout=10):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        return None


def check_env_key(key, secret=False):
    val = os.environ.get(key) or _load_env_value(key)
    if val and (secret or not val.startswith("your_")):
        return val
    return None


def _load_env_value(key):
    env_file = PROJECT_ROOT / ".env"
    if not env_file.exists():
        return None
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip().strip("\"'")
    return None


def load_env_file():
    env_file = PROJECT_ROOT / ".env"
    env = {}
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip().strip("\"'")
    return env


def check_binary(name, version_flag="--version"):
    proc = run([name, version_flag])
    if proc and proc.returncode == 0:
        ver = proc.stdout.strip().split("\n")[0][:60]
        return Check(name, PASS, ver)
    return Check(name, FAIL, f"{name} not found or not executable")


def main():
    parser = argparse.ArgumentParser(description="CreatorForge health check")
    parser.add_argument("--quiet", action="store_true", help="Only show failures")
    parser.add_argument("--fix", action="store_true", help="Attempt auto-fix for common issues")
    args = parser.parse_args()

    print()
    print("  CreatorForge Doctor")
    print("  " + dim("=" * 30))
    print()

    env = load_env_file()
    quiet = args.quiet
    fix = args.fix

    results = []

    # ── 1. Project structure ──
    if not quiet:
        print(f"  {cyan('── Environment & Structure ──')}")

    pip_installed = None
    try:
        import cryptography
        pip_installed = True
    except ImportError:
        pip_installed = False

    results.append(Check(
        "Python dependencies installed", PASS if pip_installed else FAIL,
        "" if pip_installed else "run: pip install -r requirements.txt"
    ))

    results.append(Check(
        ".env file exists", PASS if (PROJECT_ROOT / ".env").exists() else FAIL,
        "" if (PROJECT_ROOT / ".env").exists() else "cp .env.example .env"
    ))

    if (PROJECT_ROOT / ".env.example").exists():
        env_example = _load_env_value.__wrapped__ if hasattr(_load_env_value, "__wrapped__") else None
    channels_dir = PROJECT_ROOT / "channels"
    channels = [d.name for d in channels_dir.iterdir() if d.is_dir() and not d.name.startswith(".")] if channels_dir.exists() else []
    results.append(Check(
        "Channel directories exist", PASS if channels else WARN,
        f"{len(channels)} channel(s): {', '.join(channels)}" if channels else "no channels found — run creatorforge onboard"
    ))

    # ── 2. Binary tools ──
    if not quiet:
        print()
        print(f"  {cyan('── CLI Tools ──')}")
    results.append(check_binary("python3"))
    results.append(check_binary("yt-dlp"))
    results.append(check_binary("pip3") or check_binary("pip"))
    results.append(check_binary("git"))

    # ── 3. API keys ──
    if not quiet:
        print()
        print(f"  {cyan('── API Keys ──')}")

    key_checks = [
        ("LLM_API_KEY", "LLM provider (OpenAI/Ollama)"),
        ("TRANSCRIBE_API_KEY", "Transcription (Groq)"),
        ("YOUTUBE_DATA_API_KEY", "YouTube Data API"),
    ]
    for key, label in key_checks:
        val = check_env_key(key)
        results.append(Check(f"{label} ({key})", PASS if val else WARN, "" if val else "not set"))

    ig_token = check_env_key("INSTAGRAM_ACCESS_TOKEN", secret=True)
    ig_acct = check_env_key("INSTAGRAM_BUSINESS_ACCOUNT_ID")
    if ig_token and ig_acct:
        results.append(Check("Instagram Graph API", PASS))
    elif ig_token and not ig_acct:
        results.append(Check("Instagram Graph API", WARN, "token set but no business account ID"))
    else:
        results.append(Check("Instagram Graph API", WARN, "not configured — run setup-ig-token.py"))

    groq = check_env_key("GROQ_API_KEY", secret=True)
    if groq:
        results.append(Check("Groq API key", PASS, "used as transcription fallback"))
    elif not check_env_key("TRANSCRIBE_API_KEY"):
        results.append(Check("Groq API key", WARN, "neither GROQ_API_KEY nor TRANSCRIBE_API_KEY set"))

    pexels = check_env_key("PEXELS_API_KEY")
    pixabay = check_env_key("PIXABAY_API_KEY")
    if pexels or pixabay:
        results.append(Check("Stock media API", PASS, f"{'Pexels' if pexels else ''}{' + ' if pexels and pixabay else ''}{'Pixabay' if pixabay else ''}"))
    else:
        results.append(Check("Stock media API", WARN, "neither PEXELS_API_KEY nor PIXABAY_API_KEY set"))

    # ── 4. Credential encryption ──
    if not quiet:
        print()
        print(f"  {cyan('── Credential Encryption ──')}")

    key_file = PROJECT_ROOT / "data" / "recon" / "credentials.key"
    creds_file = PROJECT_ROOT / "data" / "recon" / ".credentials"
    enc_key = check_env_key("CREDENTIALS_ENCRYPTION_KEY", secret=True)
    if enc_key:
        results.append(Check("CREDENTIALS_ENCRYPTION_KEY in .env", PASS, "backed up in .env"))
    elif key_file.exists():
        results.append(Check("Fernet key file exists", PASS, dim(f"in {key_file.relative_to(PROJECT_ROOT)}")))
        results.append(Check("Fernet key backed up", WARN, "not in .env — if credentials.key is lost, encrypted creds are unrecoverable"))
    else:
        results.append(Check("Fernet key", INFO, "not yet generated — will be created on first credential save"))

    if creds_file.exists():
        try:
            raw = creds_file.read_bytes()
            from cryptography.fernet import Fernet
            if enc_key:
                Fernet(enc_key.encode()).decrypt(raw)
            elif key_file.exists():
                Fernet(key_file.read_bytes()).decrypt(raw)
            results.append(Check("Encrypted credentials readable", PASS))
        except Exception:
            results.append(Check("Encrypted credentials", FAIL, "cannot decrypt — key mismatch or corrupted file"))
    else:
        results.append(Check("Encrypted credentials", INFO, "no .credentials file yet"))

    # ── 5. OAuth tokens ──
    if not quiet:
        print()
        print(f"  {cyan('── OAuth Tokens ──')}")

    found_oauth = 0
    for channel in channels:
        token_path = channels_dir / channel / "yt-oauth-token.json"
        if token_path.exists():
            try:
                data = json.loads(token_path.read_text())
                has_refresh = bool(data.get("refresh_token"))
                expired = data.get("expired", False)
                if has_refresh:
                    found_oauth += 1
                    results.append(Check(f"YouTube OAuth ({channel})", PASS, "has refresh_token"))
                elif expired:
                    results.append(Check(f"YouTube OAuth ({channel})", WARN, "expired, no refresh_token — re-run setup-yt-oauth.py"))
                else:
                    results.append(Check(f"YouTube OAuth ({channel})", PASS, "valid"))
            except (json.JSONDecodeError, KeyError):
                results.append(Check(f"YouTube OAuth ({channel})", FAIL, "corrupted token file"))
        else:
            results.append(Check(f"YouTube OAuth ({channel})", INFO, "not set up — run setup-yt-oauth.py"))

    if not channels:
        results.append(Check("YouTube OAuth", INFO, "no channels to check"))

    # ── 6. Network connectivity ──
    if not quiet:
        print()
        print(f"  {cyan('── Network ──')}")

    import urllib.request
    import urllib.error
    endpoints = [
        ("YouTube API", "https://www.googleapis.com/youtube/v3"),
        ("Groq API", "https://api.groq.com/openai/v1"),
        ("Pexels", "https://api.pexels.com/v1"),
    ]
    for label, url in endpoints:
        try:
            urllib.request.urlopen(url, timeout=5)
            results.append(Check(f"Can reach {label}", PASS))
        except urllib.error.URLError:
            results.append(Check(f"Can reach {label}", WARN, f"{url} unreachable"))
        except Exception:
            results.append(Check(f"Can reach {label}", WARN, f"{url} unreachable (check internet)"))

    # Auto-fix if requested
    if fix:
        print()
        print(f"  {cyan('── Auto-Fix ──')}")
        fixed = 0

        if not (PROJECT_ROOT / ".env").exists() and (PROJECT_ROOT / ".env.example").exists():
            import shutil
            shutil.copy(PROJECT_ROOT / ".env.example", PROJECT_ROOT / ".env")
            print(f"  {green('✓')} Created .env from .env.example")
            fixed += 1

        if not (PROJECT_ROOT / "logs").exists():
            (PROJECT_ROOT / "logs").mkdir(parents=True, exist_ok=True)
            print(f"  {green('✓')} Created logs/ directory")
            fixed += 1

        cred_key_dir = PROJECT_ROOT / "data" / "recon"
        if not cred_key_dir.exists():
            cred_key_dir.mkdir(parents=True, exist_ok=True)
            print(f"  {green('✓')} Created data/recon/ directory")
            fixed += 1

        if not key_file.exists() and not enc_key:
            from cryptography.fernet import Fernet
            key = Fernet.generate_key()
            cred_key_dir.mkdir(parents=True, exist_ok=True)
            key_file.write_bytes(key)
            key_file.chmod(0o600)
            print(f"  {green('✓')} Generated credentials.key (chmod 600)")
            print(f"  {yellow('!')} Back up this key: add to .env as CREDENTIALS_ENCRYPTION_KEY={key.decode()}")
            fixed += 1

        if fixed == 0:
            print(f"  {dim('Nothing to fix — all checks passed.')}")
        else:
            print()

    # ── Summary ──
    print()
    print(f"  {cyan('── Summary ──')}")
    print()

    for r in results:
        if quiet and r.result == PASS:
            continue
        print(r)

    total = len(results)
    passed = sum(1 for r in results if r.result == PASS)
    warnings = sum(1 for r in results if r.result == WARN)
    failed = sum(1 for r in results if r.result == FAIL)

    print()
    print(f"  {passed}/{total} passed, {warnings} warnings, {failed} failures")
    print()

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
