#!/usr/bin/env python3
"""Remove Blackdrop-owned local configuration.

Deletes only what ``install-local.py`` created: the marked
``-- BLACKDROP START`` block in ``~/.config/hypr/bindings.lua``, the projectM
configuration Blackdrop wrote at ``~/.projectM/config.inp`` (restoring the prior
file when there was one), the old ``~/.config/projectM/config.inp`` write from
0.2.0 and earlier, and Blackdrop's own state. Unknown files left in the state
directory are preserved, so a later user edit is never silently discarded.
"""

from __future__ import annotations

import os
import shutil
import stat
from pathlib import Path

HOME = Path.home()
STATE = HOME / ".local/state/blackdrop"
CONFIG = HOME / ".projectM/config.inp"
LEGACY_CONFIG = HOME / ".config/projectM/config.inp"
BINDINGS = HOME / ".config/hypr/bindings.lua"

BACKUP_NAME = "projectm-config.before-blackdrop"
ABSENT_NAME = "projectm-config.was-absent"
LEGACY_BACKUP_NAME = "config.inp.before-blackdrop"
LEGACY_ABSENT_NAME = "projectm-config-was-absent"

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
    """Put the user's own projectM configuration back, or remove ours."""
    backup = STATE / BACKUP_NAME
    absent = STATE / ABSENT_NAME
    if absent.exists():
        CONFIG.unlink(missing_ok=True)
    elif backup.exists():
        CONFIG.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup, CONFIG)


def retire_legacy_config() -> None:
    """Undo the 0.2.0 write to the path projectM never reads.

    Only our own state decides: delete the file when we created it, restore the
    user's copy when we modified theirs, and otherwise leave it alone.
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
        pass


def main() -> int:
    remove_bindings_block()
    restore_projectm_config()
    retire_legacy_config()
    (STATE / "applied").unlink(missing_ok=True)
    (STATE / BACKUP_NAME).unlink(missing_ok=True)
    (STATE / ABSENT_NAME).unlink(missing_ok=True)
    CONFIG.with_name(CONFIG.name + ".blackdrop.tmp").unlink(missing_ok=True)
    CONFIG.with_suffix(".tmp").unlink(missing_ok=True)
    try:
        STATE.rmdir()
    except OSError:
        # Unknown files stay: never remove state this plugin did not create.
        pass
    print("Blackdrop local configuration removed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
