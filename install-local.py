#!/usr/bin/env python3
"""Apply Blackdrop's reversible local configuration.

Writes exactly two things, both owned and reversible:

1. ``~/.config/projectM/config.inp`` — the curated preset path, FPS, hard-cut
   sensitivity, and preset duration. The prior file is backed up under
   ``~/.local/state/blackdrop/`` and restored by ``remove-local.py``.
2. The ``-- BLACKDROP START`` / ``-- BLACKDROP END`` block in
   ``~/.config/hypr/bindings.lua`` — the Super+Shift+B toggle and the
   projectM window rules. Only that marked block is ever replaced.

Runs as the desktop user with no elevated privileges. Idempotent: re-running it
is the repair path.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
from datetime import datetime
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent
PRESETS = PLUGIN_DIR / "presets"

HOME = Path.home()
STATE = HOME / ".local/state/blackdrop"
MARKER = STATE / "applied"
CONFIG = HOME / ".config/projectM/config.inp"
BASE_CONFIG = Path("/usr/share/projectM/config.inp")
BINDINGS = HOME / ".config/hypr/bindings.lua"

START = "-- BLACKDROP START\n"
END = "-- BLACKDROP END\n"
BLOCK = """-- BLACKDROP START
hl.unbind("SUPER + SHIFT + B")
o.bind("SUPER + SHIFT + B", "Blackdrop", "omarchy-shell shell toggle io.github.jcarcinogen.blackdrop '{}'")
o.window({ class = "^projectM-pulseaudio$" }, { float = true })
o.window({ class = "^projectM-pulseaudio$" }, { size = { "monitor_w", "monitor_h" } })
o.window({ class = "^projectM-pulseaudio$" }, { move = { 0, 0 } })
o.window({ class = "^projectM-pulseaudio$" }, { border_size = 0, rounding = 0 })
o.window({ class = "^projectM-pulseaudio$" }, { opacity = "1 1", tag = "-default-opacity" })
-- BLACKDROP END
"""


def plugin_version() -> str:
    try:
        parsed = json.loads((PLUGIN_DIR / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "unknown"
    return str(parsed.get("version") or "unknown")


def write_atomic(path: Path, text: str, mode: int | None = None) -> None:
    """Write in place via a same-directory temporary file and one rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if mode is None:
        try:
            mode = stat.S_IMODE(path.stat().st_mode)
        except OSError:
            mode = 0o644
    temporary = path.with_name(path.name + ".blackdrop.tmp")
    with open(temporary, "w", encoding="utf-8") as handle:
        handle.write(text)
    os.chmod(temporary, mode)
    os.replace(temporary, path)


def pattern_replacement(text: str, pattern: str, replacement: str) -> str:
    text, count = re.subn(pattern, replacement, text, count=1)
    if count != 1:
        text += "\n" + replacement + "\n"
    return text


def configure_projectm() -> None:
    if not PRESETS.is_dir() or not any(PRESETS.glob("*.milk")):
        raise SystemExit(f"Blackdrop's presets are missing from {PRESETS}; reinstall the plugin.")

    STATE.mkdir(parents=True, exist_ok=True)
    backup = STATE / "config.inp.before-blackdrop"
    absent = STATE / "projectm-config-was-absent"
    if not backup.exists() and not absent.exists():
        if CONFIG.exists():
            shutil.copy2(CONFIG, backup)
        else:
            absent.touch()

    if not CONFIG.exists():
        if not BASE_CONFIG.exists():
            raise SystemExit(
                "projectM's default configuration is missing. Install the projectM "
                "packages first, then run this again."
            )
        CONFIG.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(BASE_CONFIG, CONFIG)

    try:
        text = CONFIG.read_text(encoding="utf-8")
    except OSError as error:
        raise SystemExit(f"cannot read {CONFIG}: {error}") from error

    text = pattern_replacement(
        text, r"(?m)^FPS\s*=\s*\d+.*$", "FPS  = 60                 # Frames Per Second"
    )
    text = pattern_replacement(text, r"(?m)^Fullscreen\s*=\s*\w+.*$", "Fullscreen  = false")
    text = pattern_replacement(
        text, r"(?m)^Hard Cut Sensitivity\s*=\s*[-+0-9.]+.*$", "Hard Cut Sensitivity = 3"
    )
    text = pattern_replacement(
        text, r"(?m)^Preset Duration\s*=\s*[-+0-9.]+.*$", "Preset Duration = 86400"
    )
    text = pattern_replacement(text, r"(?m)^Preset Path\s*=.*$", "Preset Path = " + str(PRESETS))
    write_atomic(CONFIG, text)


def configure_hyprland() -> None:
    try:
        text = BINDINGS.read_text(encoding="utf-8") if BINDINGS.exists() else ""
    except OSError as error:
        raise SystemExit(f"cannot read {BINDINGS}: {error}") from error

    if START in text and END in text:
        before, rest = text.split(START, 1)
        _owned, after = rest.split(END, 1)
        text = before.rstrip() + "\n\n" + BLOCK + after.lstrip()
    else:
        trimmed = text.rstrip()
        text = (trimmed + "\n\n" if trimmed else "") + BLOCK
    write_atomic(BINDINGS, text)


def record_state() -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().astimezone().isoformat(timespec="seconds")
    write_atomic(MARKER, f"version={plugin_version()}\napplied={stamp}\n")


def main() -> int:
    configure_projectm()
    configure_hyprland()
    record_state()
    print(f"Blackdrop local configuration applied ({PRESETS})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
