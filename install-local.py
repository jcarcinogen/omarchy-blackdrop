#!/usr/bin/env python3
"""Apply Blackdrop's reversible local configuration."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

HOME = Path.home()
STATE = HOME / ".local/state/blackdrop"
CONFIG = HOME / ".config/projectM/config.inp"
PRESETS = HOME / ".config/omarchy/plugins/io.github.jcarcinogen.blackdrop/presets"
BINDINGS = HOME / ".config/hypr/bindings.lua"
START = "-- BLACKDROP START\n"
END = "-- BLACKDROP END\n"
BLOCK = """-- BLACKDROP START
hl.unbind("SUPER + SHIFT + B")
o.bind("SUPER + SHIFT + B", "Blackdrop", "omarchy-shell shell toggle io.github.jcarcinogen.blackdrop '{}'")
o.window({ class = "^projectM-pulseaudio$" }, { float = true })
o.window({ class = "^projectM-pulseaudio$" }, { opacity = "1 1", tag = "-default-opacity" })
-- BLACKDROP END
"""


def configure_projectm() -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    backup = STATE / "config.inp.before-blackdrop"
    absent = STATE / "projectm-config-was-absent"
    if not backup.exists() and not absent.exists():
        if CONFIG.exists():
            shutil.copy2(CONFIG, backup)
        else:
            absent.touch()

    if not CONFIG.exists():
        default_config = Path("/usr/share/projectM/config.inp")
        if not default_config.exists():
            raise SystemExit("projectM default config is missing; install projectm first")
        CONFIG.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(default_config, CONFIG)

    text = CONFIG.read_text()
    text, count = re.subn(r"(?m)^FPS\s*=\s*\d+.*$", "FPS  = 60                 # Frames Per Second", text, count=1)
    if count != 1:
        text += "\nFPS  = 60                 # Frames Per Second\n"
    text, count = re.subn(r"(?m)^Fullscreen\s*=\s*\w+.*$", "Fullscreen  = true", text, count=1)
    if count != 1:
        text += "Fullscreen  = true\n"
    text, count = re.subn(r"(?m)^Hard Cut Sensitivity\s*=\s*[-+0-9.]+.*$", "Hard Cut Sensitivity = 3", text, count=1)
    if count != 1:
        text += "Hard Cut Sensitivity = 3\n"
    text, count = re.subn(r"(?m)^Preset Duration\s*=\s*[-+0-9.]+.*$", "Preset Duration = 86400", text, count=1)
    if count != 1:
        text += "Preset Duration = 86400\n"
    preset_line = "Preset Path = " + str(PRESETS)
    text, count = re.subn(r"(?m)^Preset Path\s*=.*$", preset_line, text, count=1)
    if count != 1:
        text += preset_line + "\n"
    CONFIG.write_text(text)


def configure_hyprland() -> None:
    text = BINDINGS.read_text() if BINDINGS.exists() else ""
    if START in text and END in text:
        before, rest = text.split(START, 1)
        _owned, after = rest.split(END, 1)
        text = before.rstrip() + "\n\n" + BLOCK + after.lstrip()
    else:
        text = text.rstrip() + "\n\n" + BLOCK
    BINDINGS.parent.mkdir(parents=True, exist_ok=True)
    BINDINGS.write_text(text)


if __name__ == "__main__":
    configure_projectm()
    configure_hyprland()
    print("Blackdrop local configuration applied")
