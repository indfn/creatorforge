#!/usr/bin/env bash
# CreatorForge — Weekly Performance Analysis
# Scheduled via cron/launchd. Collects analytics, extracts winners, updates brain.
# Idempotent: safe to run multiple times.
#
# Usage:
#   ./scripts/weekly-analyze.sh          # full run
#   ./scripts/weekly-analyze.sh --dry-run  # preview only

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PIPELINE_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PIPELINE_DIR/logs"
DRY_RUN=false

if [[ "${1:-}" == "--dry-run" ]]; then DRY_RUN=true; fi

mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/weekly-analyze.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=== Weekly Analysis Start ==="

# 1. Verify env
if [[ ! -f "$PIPELINE_DIR/.env" ]]; then
    log "ERROR: .env not found. Run setup first."
    exit 1
fi

# 2. Export .env vars
set -a
source "$PIPELINE_DIR/.env" 2>/dev/null || true
set +a

# 3. Fetch analytics for all channels
if $DRY_RUN; then
    log "DRY RUN: Would fetch analytics for all channels"
else
    log "Fetching YouTube analytics..."
    cd "$PIPELINE_DIR"
    for channel_dir in "$PIPELINE_DIR/channels"/*/; do
        channel="$(basename "$channel_dir")"
        [[ "$channel" == "_default" ]] && continue
        if [[ -f "$channel_dir/yt-oauth-token.json" ]]; then
            PYTHONPATH="$PIPELINE_DIR" python3 scripts/fetch-yt-analytics.py --channel "$channel" 2>>"$LOG_FILE" && \
                log "  Analytics fetched for $channel" || \
                log "  WARNING: Analytics fetch failed for $channel"
        else
            log "  Skipping $channel (no OAuth token)"
        fi
    done

    # 4. Update brain with insights
    log "Updating brain with insights..."
    PYTHONPATH="$PIPELINE_DIR" python3 -c "
from agent_core.recon.config import load_competitors
from pathlib import Path
import json
brain_file = Path('$PIPELINE_DIR/data/agent-brain.json')
if brain_file.exists():
    brain = json.loads(brain_file.read_text())
    brain['last_weekly_analysis'] = '$(date -u +%Y-%m-%dT%H:%M:%SZ)'
    brain_file.write_text(json.dumps(brain, indent=2))
    print('Brain updated with analysis timestamp')
" 2>>"$LOG_FILE" && log "Brain updated" || log "WARNING: Brain update failed"
fi

log "=== Weekly Analysis End ==="
