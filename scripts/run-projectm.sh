#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "$0")" && pwd)"
plugin_dir="$(cd -- "$script_dir/.." && pwd)"
preset_index="${1:-0}"
output_name="${2:-}"
[[ "$preset_index" =~ ^[0-9]+$ ]] || preset_index=0

# A marketplace install only clones the plugin; the projectM packages and the
# one-time local setup are a separate, visible user action. Fail with an
# instruction the overlay can show instead of a bare 127.
if ! command -v projectM-pulseaudio >/dev/null 2>&1; then
  printf 'Blackdrop: the projectM packages are not installed. Run %s/setup.sh to finish setup.\n' "$plugin_dir" >&2
  exit 69
fi

child=""
helper=""
cleanup() {
  if [[ -n "$helper" ]] && kill -0 "$helper" 2>/dev/null; then
    kill "$helper" 2>/dev/null || true
    wait "$helper" 2>/dev/null || true
  fi
  if [[ -n "$child" ]] && kill -0 "$child" 2>/dev/null; then
    kill -KILL "$child" 2>/dev/null || true
    wait "$child" 2>/dev/null || true
  fi
}
trap cleanup TERM INT EXIT

fps="$("$script_dir/set_projectm_fps.py" "$output_name")"
printf 'Blackdrop: projectM FPS=%s output=%s\n' "$fps" "${output_name:-focused}" >&2

projectM-pulseaudio &
child=$!
(
  "$script_dir/wait-projectm.py" "$child"
  sleep 0.2
  keys=()
  for ((i = 0; i <= preset_index; i++)); do keys+=(n); done
  keys+=(Up Up Up Up Up)
  DISPLAY="${DISPLAY:-:0}" "$script_dir/projectm-key.py" "${keys[@]}"
) &
helper=$!
wait "$child"
