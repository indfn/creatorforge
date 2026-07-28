#!/usr/bin/env bash
# CreatorForge — Daily Competitor Discovery
# Scheduled via cron/launchd. Scrapes competitors, scores new topics, saves to topics/.
# Idempotent: safe to run multiple times.
#
# Usage:
#   ./scripts/daily-discover.sh          # full run
#   ./scripts/daily-discover.sh --dry-run  # preview only

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PIPELINE_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PIPELINE_DIR/logs"
DRY_RUN=false

if [[ "${1:-}" == "--dry-run" ]]; then DRY_RUN=true; fi

mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/daily-discover.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=== Daily Discover Start ==="

# 1. Verify env
if [[ ! -f "$PIPELINE_DIR/.env" ]]; then
    log "ERROR: .env not found. Run setup first."
    exit 1
fi

# 2. Export .env vars
set -a
source "$PIPELINE_DIR/.env" 2>/dev/null || true
set +a

# 3. Run recon pipeline (competitor scraping)
log "Starting competitor recon..."
if $DRY_RUN; then
    log "DRY RUN: Would run: python3 -m agent_core.recon.pipeline"
else
    cd "$PIPELINE_DIR"
    PYTHONPATH="$PIPELINE_DIR" python3 -m agent_core.recon.pipeline 2>>"$LOG_FILE" && \
        log "Competitor recon complete" || \
        log "WARNING: Competitor recon had issues (see above)"
fi

log "=== Daily Discover End ==="
