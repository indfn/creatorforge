#!/usr/bin/env python3
"""
Fernet encryption key — backup & restore tool.

The credentials.key file is critical — if lost, all stored credentials
(IG passwords, API keys in the encrypted store) become unrecoverable.

Usage:
    python scripts/backup-credentials-key.py            # show current key location & status
    python scripts/backup-credentials-key.py --export   # print key to stdout (pipe to file)
    python scripts/backup-credentials-key.py --to-env   # save CREDENTIALS_ENCRYPTION_KEY into .env
"""

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
KEY_FILE = PROJECT_ROOT / "data" / "recon" / "credentials.key"
ENV_PATH = PROJECT_ROOT / ".env"

DIM = "\033[2m"
GREEN = "\033[1;32m"
YELLOW = "\033[1;33m"
RESET = "\033[0m"


def dim(t): return f"{DIM}{t}{RESET}"
def green(t): return f"{GREEN}{t}{RESET}"
def yellow(t): return f"{YELLOW}{t}{RESET}"


def main():
    parser = argparse.ArgumentParser(description="Fernet key backup tool")
    parser.add_argument("--export", action="store_true", help="Print the key to stdout")
    parser.add_argument("--to-env", action="store_true", help="Save CREDENTIALS_ENCRYPTION_KEY into .env")
    args = parser.parse_args()

    if not KEY_FILE.exists():
        print()
        print("  Fernet key not yet generated.")
        print(f"  It will be created automatically on first credential save.")
        print(f"  Path: {dim(str(KEY_FILE))}")
        print()
        sys.exit(0)

    key = KEY_FILE.read_text().strip()

    if args.export:
        print(key)
        print(f"  {dim('(key copied to stdout — pipe to a file or password manager)')}", file=sys.stderr)
        return

    if args.to_env:
        if not ENV_PATH.exists():
            ENV_PATH.write_text(f"CREDENTIALS_ENCRYPTION_KEY={key}\n")
        else:
            lines = ENV_PATH.read_text().splitlines()
            found = False
            for i, line in enumerate(lines):
                if line.strip().startswith("CREDENTIALS_ENCRYPTION_KEY="):
                    lines[i] = f"CREDENTIALS_ENCRYPTION_KEY={key}"
                    found = True
                    break
            if not found:
                lines.append(f"\n# Fernet encryption key (backup — mirrors data/recon/credentials.key)")
                lines.append(f"CREDENTIALS_ENCRYPTION_KEY={key}")
            ENV_PATH.write_text("\n".join(lines) + "\n")
        print(f"  {green('✓')} CREDENTIALS_ENCRYPTION_KEY written to {dim(str(ENV_PATH))}")
        return

    # Default: show status
    print()
    print("  Fernet Encryption Key")
    print(f"  {dim('─' * 30)}")
    print(f"  Location:  {dim(str(KEY_FILE))}")
    print(f"  Key:       {key[:12]}...{key[-8:]}" if len(key) > 20 else f"  Key:       {key}")
    print()
    print(f"  {yellow('⚠')}  If you lose this key, all encrypted credentials become unrecoverable.")
    print()
    print(f"  Backup options:")
    print(f"    {green('1)')} python scripts/backup-credentials-key.py --to-env")
    print(f"       → copies key into .env as CREDENTIALS_ENCRYPTION_KEY")
    print()
    print(f"    {green('2)')} python scripts/backup-credentials-key.py --export > ~/creatorforge-key.txt")
    print(f"       → saves to a file (store somewhere safe)")
    print()


if __name__ == "__main__":
    main()
