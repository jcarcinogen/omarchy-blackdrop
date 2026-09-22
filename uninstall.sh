#!/usr/bin/env bash
set -euo pipefail

PLUGIN_ID="io.github.jcarcinogen.blackdrop"
PLUGIN_DIR="$HOME/.config/omarchy/plugins/$PLUGIN_ID"

export OMARCHY_PATH="${OMARCHY_PATH:-/usr/share/omarchy}"

omarchy-shell shell hide "$PLUGIN_ID" 2>/dev/null || true
omarchy plugin disable "$PLUGIN_ID" 2>/dev/null || true
pkill -x projectM-pulseaudio 2>/dev/null || true
python3 "$PLUGIN_DIR/remove-local.py"
hyprctl reload >/dev/null 2>&1 || true
rm -rf "$PLUGIN_DIR"
omarchy-shell shell rescanPlugins >/dev/null 2>&1 || true
printf 'Blackdrop removed. Its binding, window rules, and projectM configuration were restored.\n'
printf 'The projectM packages were left installed; remove them with: omarchy pkg remove projectm projectm-pulseaudio\n'
