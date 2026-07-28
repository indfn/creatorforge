#!/usr/bin/env bash
# CreatorForge — Cron / launchd Uninstaller
# Removes daily-discover and weekly-analyze scheduled jobs.
#
# Usage:
#   ./scripts/uninstall-crons.sh            # uninstall for current platform
#   ./scripts/uninstall-crons.sh --dry-run  # preview without uninstalling
#   ./scripts/uninstall-crons.sh --macos    # force macOS launchd uninstall

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

uninstall_macos() {
    local PLIST_DIR="$HOME/Library/LaunchAgents"

    for plist in "$PIPELINE_DIR/cron/com.creatorforge."*.plist; do
        local name="$(basename "$plist")"
        local target="$PLIST_DIR/$name"

        if [[ ! -f "$target" ]]; then
            continue
        fi

        if $DRY_RUN; then
            dim "  Would unload and remove: $name"
            continue
        fi

        launchctl unload "$target" 2>/dev/null && success "$name unloaded" || warn "$name not loaded"
        rm "$target" && success "$name removed from LaunchAgents" || warn "Could not remove $target"
    done
}

uninstall_linux() {
    echo ""
    announce "To remove cron jobs, run:"
    echo "  crontab -e"
    echo ""
    announce "Remove the CreatorForge lines (look for daily-discover and weekly-analyze)."
    echo ""
    announce "To remove systemd timers (if used):"
    echo "  sudo systemctl disable --now creatorforge-daily.timer creatorforge-weekly.timer 2>/dev/null || true"
    echo "  sudo rm /etc/systemd/system/creatorforge-*.{timer,service} 2>/dev/null || true"
}

echo ""
echo "  CreatorForge — Cron Uninstaller"
echo ""

OS="$(detect_os)"
case "$OS" in
    macos)    uninstall_macos ;;
    linux)    uninstall_linux ;;
    *)        warn "Unsupported OS: $(uname -s)"; exit 1 ;;
esac

echo ""
$DRY_RUN && dim "(dry run — no changes made)"
echo ""
