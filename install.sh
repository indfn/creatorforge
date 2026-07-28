#!/usr/bin/env bash
# CreatorForge — One-line installer
# Usage: bash <(curl -fsSL https://raw.githubusercontent.com/charlesdove977/goviralbro/main/install.sh)

set -euo pipefail

BLUE='\033[1;34m'
CYAN='\033[1;36m'
WHITE='\033[1;37m'
GREEN='\033[1;32m'
DIM='\033[2m'
RESET='\033[0m'

show_logo() {
    echo ""
    echo -e "${BLUE}    ██████╗██████╗ ███████╗ █████╗ ████████╗ ██████╗ ██████╗ ${RESET}"
    echo -e "${BLUE}   ██╔════╝██╔══██╗██╔════╝██╔══██╗╚══██╔══╝██╔═══██╗██╔══██╗${RESET}"
    echo -e "${BLUE}   ██║     ██████╔╝█████╗  ███████║   ██║   ██║   ██║██████╔╝${RESET}"
    echo -e "${BLUE}   ██║     ██╔══██╗██╔══╝  ██╔══██║   ██║   ██║   ██║██╔══██╗${RESET}"
    echo -e "${BLUE}   ╚██████╗██║  ██║███████╗██║  ██║   ██║   ╚██████╔╝██║  ██║${RESET}"
    echo -e "${BLUE}    ╚═════╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝${RESET}"
    echo ""
    echo -e "   ${WHITE}CreatorForge${RESET} ${DIM}v0.2.0${RESET}"
    echo -e "   ${DIM}AI-powered content creation suite for OpenCode.${RESET}"
    echo ""
}

show_logo

# Check for git
if ! command -v git &> /dev/null; then
    echo -e "${BLUE}✗${RESET} git not found. Install git first."
    exit 1
fi

# Check for OpenCode
if ! command -v opencode &> /dev/null; then
    echo -e "${BLUE}!${RESET} OpenCode CLI not detected. You'll need it to run commands."
    echo -e "${DIM}  Install: https://opencode.ai${RESET}"
    echo ""
fi

# Clone
INSTALL_DIR="creatorforge"
if [[ -d "$INSTALL_DIR" ]]; then
    echo -e "${BLUE}!${RESET} Directory '$INSTALL_DIR' already exists."
    echo -e "${DIM}  cd $INSTALL_DIR && bash scripts/init-creatorforge.sh${RESET}"
    exit 1
fi

echo -e "${BLUE}↓${RESET} Cloning repository..."
git clone --depth 1 https://github.com/charlesdove977/goviralbro.git "$INSTALL_DIR" 2>/dev/null
echo -e "${GREEN}✓${RESET} Cloned CreatorForge"

cd "$INSTALL_DIR"

# Run bootstrap
echo -e "${BLUE}↓${RESET} Running bootstrap..."
bash scripts/init-creatorforge.sh 2>/dev/null || true
echo -e "${GREEN}✓${RESET} Initialized CreatorForge"

# Setup env
if [[ ! -f .env ]] && [[ -f .env.example ]]; then
    cp .env.example .env
    echo -e "${GREEN}✓${RESET} Created .env from template"
fi

echo ""
echo -e "${GREEN}Done!${RESET} Run ${CYAN}creatorforge doctor${RESET} to verify setup, then ${CYAN}opencode .${RESET} to start."
echo ""
