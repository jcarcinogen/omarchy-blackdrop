#!/usr/bin/env bash
# Blackdrop one-time setup.
#
# Installs the projectM packages Blackdrop renders with, then applies
# Blackdrop's reversible local configuration (the curated preset path plus the
# Super+Shift+B toggle and the projectM window rules), then reloads Hyprland so
# the new binding is live.
#
# Idempotent: re-running it is the repair path. It never touches Omarchy's
# screensaver launcher, and it removes nothing Blackdrop does not own.

set -euo pipefail

plugin_dir="$(cd -- "$(dirname -- "$0")" && pwd)"
export OMARCHY_PATH="${OMARCHY_PATH:-/usr/share/omarchy}"

say() { printf '%s\n' "$*"; }

cat <<'BANNER'
Blackdrop setup
===============
Step 1 installs the projectM packages. Step 2 applies Blackdrop's reversible
local configuration. Step 3 reloads Hyprland so the toggle works immediately.

Re-running this script is safe.
BANNER

say ""
say "Step 1/3 — projectM packages"
say "Omarchy's package helper asks for the normal pacman authorization here."
omarchy-pkg-add projectm projectm-pulseaudio

say ""
say "Step 2/3 — Blackdrop local configuration"
python3 "$plugin_dir/install-local.py"

say ""
say "Step 3/3 — reloading Hyprland"
hyprctl reload >/dev/null 2>&1 || say "  (hyprctl reload skipped: no live Hyprland session)"

errors="$(hyprctl configerrors 2>/dev/null || true)"
if [[ -n "${errors//[[:space:]]/}" && "$errors" != "no errors" ]]; then
  say "Hyprland reported configuration messages:"
  say "$errors"
fi

say ""
if python3 "$plugin_dir/scripts/status.py"; then
  cat <<'DONE'

Setup complete.

Press Escape to close this window, then click the droplet on the bar — or
press Super+Shift+B — to start Blackdrop.
DONE
else
  cat <<'FAILED' >&2

Blackdrop is still not ready; the checklist above names what is left.
Fix that item and run this script again, or open an issue with that output.
FAILED
  exit 1
fi
