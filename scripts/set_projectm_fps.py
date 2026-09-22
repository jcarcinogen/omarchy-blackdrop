#!/usr/bin/env python3
"""Match projectM's render FPS to the active output's current refresh rate."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

CONFIG = Path.home() / ".projectM/config.inp"


def refresh_for_monitor(monitor: dict) -> int:
    try:
        refresh = round(float(monitor.get("refreshRate", 60)))
    except (TypeError, ValueError):
        refresh = 60
    return max(30, min(360, refresh))


def choose_monitor(monitors: list[dict], requested: str) -> dict:
    if requested:
        for monitor in monitors:
            if str(monitor.get("name", "")) == requested:
                return monitor
    for monitor in monitors:
        if monitor.get("focused") is True:
            return monitor
    return monitors[0] if monitors else {"refreshRate": 60}


def update_config(path: Path, fps: int) -> bool:
    """Rewrite the FPS line in place. Returns False when projectM is not set up yet.

    Only that one line changes: every other byte stays, including the file's own
    line endings, so this can run on each launch without churning projectM's
    configuration.
    """
    if not path.is_file():
        return False
    data = path.read_bytes()
    replacement = f"FPS  = {fps}                 # Frames Per Second".encode()
    data, count = re.subn(rb"(?m)^FPS\s*=[^\r\n]*", replacement, data, count=1)
    if count != 1:
        ending = b"\r\n" if b"\r\n" in data else b"\n"
        if data and not data.endswith((b"\n", b"\r")):
            data += ending
        data += replacement + ending
    temporary = path.with_suffix(".tmp")
    temporary.write_bytes(data)
    temporary.chmod(path.stat().st_mode)
    temporary.replace(path)
    return True


def main() -> int:
    requested = sys.argv[1] if len(sys.argv) > 1 else ""
    monitors = json.loads(subprocess.check_output(["hyprctl", "-j", "monitors", "all"], text=True, timeout=3))
    monitor = choose_monitor(monitors, requested)
    fps = refresh_for_monitor(monitor)
    if not update_config(CONFIG, fps):
        # Marketplace installs reach this before the one-time setup has run.
        # Report the FPS and keep going rather than failing the launcher.
        print(f"Blackdrop: {CONFIG} not found; run this plugin's setup.sh", file=sys.stderr)
    print(fps, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
