#!/usr/bin/env python3
"""Make the projectM child fullscreen without stealing focus from the overlay."""

from __future__ import annotations

import json
import subprocess
import sys
import time

pid = int(sys.argv[1])
for _ in range(60):
    try:
        clients = json.loads(subprocess.check_output(["hyprctl", "-j", "clients"], text=True, timeout=2))
        client = next((item for item in clients if int(item.get("pid", -1)) == pid), None)
        if client:
            address = str(client["address"])
            action = f'hl.dsp.window.fullscreen({{ mode = "fullscreen", window = "address:{address}" }})'
            subprocess.run(["hyprctl", "dispatch", action], check=True, stdout=subprocess.DEVNULL, timeout=2)
            raise SystemExit(0)
    except (OSError, subprocess.SubprocessError, ValueError, json.JSONDecodeError):
        pass
    time.sleep(0.1)
raise SystemExit("projectM window did not map")
