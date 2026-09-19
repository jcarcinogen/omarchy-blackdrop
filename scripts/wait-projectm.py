#!/usr/bin/env python3
"""Wait until the projectM child has mapped in Hyprland."""

from __future__ import annotations

import json
import subprocess
import sys
import time

pid = int(sys.argv[1])
for _ in range(60):
    try:
        clients = json.loads(subprocess.check_output(["hyprctl", "-j", "clients"], text=True, timeout=2))
        if any(int(item.get("pid", -1)) == pid for item in clients):
            raise SystemExit(0)
    except (OSError, subprocess.SubprocessError, ValueError, json.JSONDecodeError):
        pass
    time.sleep(0.1)
raise SystemExit("projectM window did not map")
