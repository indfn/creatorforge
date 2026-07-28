#!/usr/bin/env bash
# DEPRECATED: Use ./scripts/init-creatorforge.sh instead.
# This script is kept for backward compatibility with v0.1 installs.
# It now delegates to init-creatorforge.sh.

echo ""
echo "  ⚠  init-viral-command.sh is DEPRECATED."
echo "     Use init-creatorforge.sh instead."
echo ""
echo "  Running init-creatorforge.sh now..."
echo ""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$SCRIPT_DIR/init-creatorforge.sh" "$@"
