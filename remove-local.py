#!/usr/bin/env python3
"""Remove Blackdrop-owned local configuration."""

from __future__ import annotations

import shutil
from pathlib import Path

HOME = Path.home()
STATE = HOME / ".local/state/blackdrop"
CONFIG = HOME / ".config/projectM/config.inp"
BINDINGS = HOME / ".config/hypr/bindings.lua"
START = "-- BLACKDROP START\n"
END = "-- BLACKDROP END\n"

if BINDINGS.exists():
    text = BINDINGS.read_text()
    if START in text and END in text:
        before, rest = text.split(START, 1)
        _owned, after = rest.split(END, 1)
        BINDINGS.write_text(before.rstrip() + "\n" + after.lstrip())

absent = STATE / "projectm-config-was-absent"
backup = STATE / "config.inp.before-blackdrop"
if absent.exists():
    CONFIG.unlink(missing_ok=True)
elif backup.exists():
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(backup, CONFIG)

absent.unlink(missing_ok=True)
backup.unlink(missing_ok=True)
try:
    STATE.rmdir()
except OSError:
    pass
