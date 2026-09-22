#!/usr/bin/env python3
"""Remove Blackdrop-owned local configuration.

Deletes only what ``install-local.py`` created: the marked
``-- BLACKDROP START`` block in ``~/.config/hypr/bindings.lua``, the projectM
configuration Blackdrop wrote (restoring the prior file when there was one),
and Blackdrop's own state marker. Unknown files left in the state directory are
preserved, so a later user edit is never silently discarded.
"""

from __future__ import annotations

import os
import shutil
import stat
from pathlib import Path

HOME = Path.home()
STATE = HOME / ".local/state/blackdrop"
CONFIG = HOME / ".config/projectM/config.inp"
BINDINGS = HOME / ".config/hypr/bindings.lua"

START = "-- BLACKDROP START\n"
END = "-- BLACKDROP END\n"


def write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        mode = stat.S_IMODE(path.stat().st_mode)
    except OSError:
        mode = 0o644
    temporary = path.with_name(path.name + ".blackdrop.tmp")
    with open(temporary, "w", encoding="utf-8") as handle:
        handle.write(text)
    os.chmod(temporary, mode)
    os.replace(temporary, path)


def remove_bindings_block() -> None:
    if not BINDINGS.exists():
        return
    text = BINDINGS.read_text(encoding="utf-8")
    if START not in text or END not in text:
        return
    before, rest = text.split(START, 1)
    _owned, after = rest.split(END, 1)
    write_atomic(BINDINGS, before.rstrip() + "\n" + after.lstrip())


def restore_projectm_config() -> None:
    absent = STATE / "projectm-config-was-absent"
    backup = STATE / "config.inp.before-blackdrop"
    if absent.exists():
        CONFIG.unlink(missing_ok=True)
    elif backup.exists():
        CONFIG.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup, CONFIG)


def main() -> int:
    remove_bindings_block()
    restore_projectm_config()
    (STATE / "applied").unlink(missing_ok=True)
    (STATE / "projectm-config-was-absent").unlink(missing_ok=True)
    (STATE / "config.inp.before-blackdrop").unlink(missing_ok=True)
    CONFIG.with_name(CONFIG.name + ".blackdrop.tmp").unlink(missing_ok=True)
    try:
        STATE.rmdir()
    except OSError:
        # Unknown files stay: never remove state this plugin did not create.
        pass
    print("Blackdrop local configuration removed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
