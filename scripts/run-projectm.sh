#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "$0")" && pwd)"
preset_index="${1:-0}"
[[ "$preset_index" =~ ^[0-9]+$ ]] || preset_index=0
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
