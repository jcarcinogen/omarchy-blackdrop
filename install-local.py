#!/usr/bin/env python3
"""Apply Blackdrop's reversible local configuration.

Writes exactly two things, both owned and reversible:

1. ``~/.projectM/config.inp`` — the curated preset path, FPS, hard-cut
   sensitivity, and preset duration. This is the file projectM reports opening
   (``[projectM] config file: ~/.projectM/config.inp``); 0.2.0 and earlier wrote
   ``~/.config/projectM/config.inp``, which projectM never reads, so projectM
   kept its stock landing preset and the plugin looked like it was not
   working. ``retire_legacy_config`` cleans that old path up. The prior file at
   the real path is backed up under ``~/.local/state/blackdrop/`` and restored
   by ``remove-local.py``.
2. The ``-- BLACKDROP START`` / ``-- BLACKDROP END`` block in
   ``~/.config/hypr/bindings.lua`` — the Super+Shift+B toggle and the
   projectM window rules. Only that marked block is ever replaced.

The config edit rewrites individual keys in place: every other byte, including
the file's own line endings, is passed through unchanged.

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

# The path projectM itself opens. Verified against its own startup output.
CONFIG = HOME / ".projectM/config.inp"
# Where 0.2.0 and earlier wrote. projectM does not read it; retired on install.
LEGACY_CONFIG = HOME / ".config/projectM/config.inp"
BASE_CONFIG = Path("/usr/share/projectM/config.inp")
BINDINGS = HOME / ".config/hypr/bindings.lua"

BACKUP_NAME = "projectm-config.before-blackdrop"
ABSENT_NAME = "projectm-config.was-absent"
LEGACY_BACKUP_NAME = "config.inp.before-blackdrop"
LEGACY_ABSENT_NAME = "projectm-config-was-absent"

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

# projectM's own keys for "render what Blackdrop ships, at display rate, and
# never auto-advance away from the chosen preset".
CONFIG_KEYS = (
    (b"FPS", "FPS  = 60                 # Frames Per Second"),
    (b"Fullscreen", "Fullscreen  = false"),
    (b"Hard Cut Sensitivity", "Hard Cut Sensitivity = 3"),
    (b"Preset Duration", "Preset Duration = 86400"),
)


def plugin_version() -> str:
    try:
        parsed = json.loads((PLUGIN_DIR / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "unknown"
    return str(parsed.get("version") or "unknown")


def write_atomic(path: Path, text: str, mode: int | None = None) -> None:
    """Write text in place via a same-directory temporary file and one rename."""
    write_atomic_bytes(path, text.encode("utf-8"), mode)


def write_atomic_bytes(path: Path, data: bytes, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if mode is None:
        try:
            mode = stat.S_IMODE(path.stat().st_mode)
        except OSError:
            mode = 0o644
    temporary = path.with_name(path.name + ".blackdrop.tmp")
    with open(temporary, "wb") as handle:
        handle.write(data)
    os.chmod(temporary, mode)
    os.replace(temporary, path)


def key_replacement(data: bytes, key: bytes, replacement: str) -> bytes:
    """Rewrite one ``key = value`` line, leaving every other byte alone."""
    pattern = re.compile(rb"(?m)^" + re.escape(key) + rb"\s*=[^\r\n]*")
    data, count = pattern.subn(replacement.encode("utf-8"), data, count=1)
    if count == 0:
        ending = b"\r\n" if b"\r\n" in data else b"\n"
        if data and not data.endswith((b"\n", b"\r")):
            data += ending
        data += replacement.encode("utf-8") + ending
    return data


def pattern_replacement(text: str, pattern: str, replacement: str) -> str:
    text, count = re.subn(pattern, replacement, text, count=1)
    if count != 1:
        text += "\n" + replacement + "\n"
    return text


def retire_legacy_config() -> None:
    """Undo the earlier write to the path projectM never reads.

    Only the state files this plugin wrote decide what happens: if we created
    that file it is deleted, if we modified the user's own file it is restored,
    and if we have no record of it the file is left exactly where it is.
    """
    legacy_backup = STATE / LEGACY_BACKUP_NAME
    legacy_absent = STATE / LEGACY_ABSENT_NAME
    if legacy_absent.exists():
        LEGACY_CONFIG.unlink(missing_ok=True)
    elif legacy_backup.exists() and LEGACY_CONFIG.exists():
        shutil.copy2(legacy_backup, LEGACY_CONFIG)
    legacy_backup.unlink(missing_ok=True)
    legacy_absent.unlink(missing_ok=True)
    LEGACY_CONFIG.with_name(LEGACY_CONFIG.name + ".blackdrop.tmp").unlink(missing_ok=True)
    try:
        LEGACY_CONFIG.parent.rmdir()
    except OSError:
        # Never remove a directory that still holds something else.
        pass


def configure_projectm() -> None:
    if not PRESETS.is_dir() or not any(PRESETS.glob("*.milk")):
        raise SystemExit(f"Blackdrop's presets are missing from {PRESETS}; reinstall the plugin.")

    STATE.mkdir(parents=True, exist_ok=True)
    retire_legacy_config()

    backup = STATE / BACKUP_NAME
    absent = STATE / ABSENT_NAME
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
        data = CONFIG.read_bytes()
    except OSError as error:
        raise SystemExit(f"cannot read {CONFIG}: {error}") from error

    for key, replacement in (*CONFIG_KEYS, (b"Preset Path", "Preset Path = " + str(PRESETS))):
        data = key_replacement(data, key, replacement)
    write_atomic_bytes(CONFIG, data)


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
