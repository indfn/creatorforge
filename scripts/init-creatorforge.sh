#!/usr/bin/env bash
# CreatorForge — Repository Bootstrap Script
# Usage: ./scripts/init-creatorforge.sh
# Idempotent: safe to run multiple times

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PIPELINE_DIR="$(dirname "$SCRIPT_DIR")"

FORCE=false
if [[ "${1:-}" == "--force" ]]; then FORCE=true; fi

BLUE='\033[1;34m'
CYAN='\033[1;36m'
GREEN='\033[1;32m'
WHITE='\033[1;37m'
DIM='\033[2m'
RESET='\033[0m'

echo ""
echo -e "${BLUE}    ██████╗██████╗ ███████╗ █████╗ ████████╗ ██████╗ ██████╗ ${RESET}"
echo -e "${BLUE}   ██╔════╝██╔══██╗██╔════╝██╔══██╗╚══██╔══╝██╔═══██╗██╔══██╗${RESET}"
echo -e "${BLUE}   ██║     ██████╔╝█████╗  ███████║   ██║   ██║   ██║██████╔╝${RESET}"
echo -e "${BLUE}   ██║     ██╔══██╗██╔══╝  ██╔══██║   ██║   ██║   ██║██╔══██╗${RESET}"
echo -e "${BLUE}   ╚██████╗██║  ██║███████╗██║  ██║   ██║   ╚██████╔╝██║  ██║${RESET}"
echo -e "${BLUE}    ╚═════╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝${RESET}"
echo ""
echo -e "   ${WHITE}CreatorForge${RESET} ${DIM}v0.2.0${RESET}"
echo -e "   ${DIM}AI-powered content creation suite for OpenCode/Claude Code.${RESET}"
echo ""

# Verify we're in the right repo
if [[ ! -d "$PIPELINE_DIR/.opencode/commands" ]]; then
    echo "ERROR: Not running from the CreatorForge repo root."
    echo "Expected .opencode/commands/ directory at: $PIPELINE_DIR/.opencode/commands/"
    echo "Usage: cd /path/to/creatorforge && ./scripts/init-creatorforge.sh"
    exit 1
fi
echo "✓ Running from: $PIPELINE_DIR"
echo ""

# Step 1: Create directory structure
echo "Step 1: Creating directory structure..."

DIRS=(
    "data/recon/competitors"
    "data/recon/reports"
    "logs"
)

CREATED=0
for dir in "${DIRS[@]}"; do
    target="$PIPELINE_DIR/$dir"
    if [[ ! -d "$target" ]]; then
        mkdir -p "$target"; ((CREATED++))
    fi
done
# Ensure default channel structure
if [[ ! -f "$PIPELINE_DIR/channels/Default/brain.json" ]]; then
    mkdir -p "$PIPELINE_DIR/channels/Default/data/"{topics,hooks,insights,analytics,recon}
    mkdir -p "$PIPELINE_DIR/channels/Default/active_production/"{assets,render}
    cp "$PIPELINE_DIR/channels/ChannelA/brain.json" "$PIPELINE_DIR/channels/Default/brain.json" 2>/dev/null || true
    cp "$PIPELINE_DIR/channels/ChannelA/channel_config.json" "$PIPELINE_DIR/channels/Default/channel_config.json" 2>/dev/null || true
    echo "  ✓ Default channel created"
fi
echo "  ✓ Directories ready ($CREATED created)"
echo ""

# Step 2: Initialize empty data files
echo "Step 2: Initializing data files..."
touch "$PIPELINE_DIR/data/hooks.jsonl" 2>/dev/null || true
echo "  ✓ Data files ready"
echo ""

# Step 3: Install Python dependencies
echo "Step 3: Installing Python dependencies..."
DEPS_STATUS="OK"
if [[ -f "$PIPELINE_DIR/requirements.txt" ]]; then
    if command -v pip3 &>/dev/null; then
        pip3 install -r "$PIPELINE_DIR/requirements.txt" --quiet 2>/dev/null && \
            echo "  ✓ Python packages installed" || \
            { echo "  ⚠ Some packages failed"; DEPS_STATUS="ISSUES"; }
    else
        echo "  ⚠ pip3 not found"; DEPS_STATUS="ISSUES"
    fi
fi
echo ""

# Step 4: Check CLI tools
echo "Step 4: Checking CLI tools..."
command -v python3 &>/dev/null && echo "  ✓ $(python3 --version)" || echo "  ⚠ python3 not found"
command -v yt-dlp &>/dev/null && echo "  ✓ yt-dlp $(yt-dlp --version 2>&1)" || echo "  ⚠ yt-dlp not found"
command -v instaloader &>/dev/null && echo "  ✓ Instaloader" || echo "  ⚠ Instaloader not found"
echo ""

# Step 5: Check .env file
echo "Step 5: Checking API key configuration..."
ENV_FILE="$PIPELINE_DIR/.env"
ENV_STATUS="configured"
if [[ -f "$ENV_FILE" ]]; then
    echo "  ✓ .env file found"
else
    cp "$PIPELINE_DIR/.env.example" "$ENV_FILE" 2>/dev/null && \
        echo "  ✓ Created .env from template (edit to add your keys)" || \
        echo "  ⚠ Could not create .env"
    ENV_STATUS="edit .env"
fi
echo ""

# Step 6: Summary
echo ""
echo -e "  ${GREEN}✓${RESET} CreatorForge initialized"
echo ""
echo -e "  Directories:  OK"
echo -e "  Dependencies: $DEPS_STATUS"
echo -e "  API keys:     $ENV_STATUS"
echo ""
echo -e "  Next steps:"
echo -e "    1. Run ${CYAN}python scripts/setup-env.py${RESET} to configure API keys interactively"
echo -e "    2. Run ${CYAN}python scripts/doctor.py${RESET} to verify setup"
echo -e "    3. Run ${CYAN}python scripts/setup-ig-token.py${RESET} to configure Instagram (if needed)"
echo -e "    4. Run ${CYAN}python scripts/setup-yt-oauth.py --channel Default${RESET} to configure YouTube (if needed)"
echo ""
