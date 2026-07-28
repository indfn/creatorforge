#!/usr/bin/env bash
# CreatorForge — Cron / launchd Installer
# Installs daily-discover and weekly-analyze scheduled jobs.
#
# Usage:
#   ./scripts/install-crons.sh            # interactive, detect platform
#   ./scripts/install-crons.sh --dry-run  # preview without installing
#   ./scripts/install-crons.sh --macos    # force macOS launchd install
#   ./scripts/install-crons.sh --linux    # force Linux crontab instructions

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PIPELINE_DIR="$(dirname "$SCRIPT_DIR")"
DRY_RUN=false
FORCE_OS=""

for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=true ;;
        --macos) FORCE_OS="macos" ;;
        --linux) FORCE_OS="linux" ;;
    esac
done

BLUE='\033[1;34m'
GREEN='\033[1;32m'
DIM='\033[2m'
YELLOW='\033[1;33m'
RESET='\033[0m'

announce() { echo -e "${BLUE}•${RESET} $1"; }
success()  { echo -e "${GREEN}✓${RESET} $1"; }
warn()     { echo -e "${YELLOW}⚠${RESET} $1"; }
dim()      { echo -e "${DIM}$1${RESET}"; }

detect_os() {
    if [[ -n "$FORCE_OS" ]]; then
        echo "$FORCE_OS"
        return
    fi
    case "$(uname -s)" in
        Darwin) echo "macos" ;;
        Linux)  echo "linux" ;;
        *)      echo "other" ;;
    esac
}

install_macos() {
    announce "Installing launchd plists..."

    local PLIST_DIR="$HOME/Library/LaunchAgents"
    mkdir -p "$PLIST_DIR"

    for plist in "$PIPELINE_DIR/cron/com.creatorforge."*.plist; do
        local name="$(basename "$plist")"
        local target="$PLIST_DIR/$name"

        if $DRY_RUN; then
            dim "  Would install: $target"
            continue
        fi

        # Substitute __PIPELINE_DIR__ with the real path
        sed "s|__PIPELINE_DIR__|$PIPELINE_DIR|g" "$plist" > "$target"

        # Unload first if already loaded (idempotent)
        launchctl unload "$target" 2>/dev/null || true

        # Load into launchd
        if launchctl load "$target" 2>/dev/null; then
            success "$name installed and loaded"
        else
            warn "$name installed but failed to load — check $target"
        fi
    done

    echo ""
    announce "Verify with: launchctl list | grep creatorforge"
    announce "Logs at: $PIPELINE_DIR/logs/"
}

install_linux() {
    echo ""
    announce "Linux — add these lines to crontab (crontab -e):"
    echo ""
    dim "  # CreatorForge — Daily Discovery (6 AM UTC)"
    echo "  0 6 * * * cd $PIPELINE_DIR && ./scripts/daily-discover.sh >> $PIPELINE_DIR/logs/daily-discover.log 2>&1"
    echo ""
    dim "  # CreatorForge — Weekly Analysis (Friday 6 AM UTC)"
    echo "  0 6 * * 5 cd $PIPELINE_DIR && ./scripts/weekly-analyze.sh >> $PIPELINE_DIR/logs/weekly-analyze.log 2>&1"
    echo ""
    announce "Or use systemd timers — see docs/CRON-SETUP.md"
}

# ── Main ──
echo ""
echo "  CreatorForge — Cron Installer"
echo ""

OS="$(detect_os)"
case "$OS" in
    macos)
        install_macos
        ;;
    linux)
        install_linux
        ;;
    *)
        warn "Unsupported OS: $(uname -s)"
        echo "  Manual setup: see docs/CRON-SETUP.md"
        exit 1
        ;;
esac

echo ""
$DRY_RUN && dim "(dry run — no changes made)"
echo ""
