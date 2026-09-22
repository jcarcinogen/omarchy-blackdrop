#!/usr/bin/env python3
"""Read-only readiness probe for Blackdrop.

This probe never writes a file, never asks for elevated privileges, and never
launches anything that changes state. It reports whether the projectM packages
and Blackdrop's reversible local configuration are in place so the plugin can
show a setup card instead of failing silently.

Exit status is always 0: the JSON body is the contract, and `ready` is the flag.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import sys
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parents[1]
PRESETS_DIR = PLUGIN_DIR / "presets"
USER_CONFIG = Path.home() / ".config/projectM/config.inp"
BASE_CONFIG = Path("/usr/share/projectM/config.inp")
BINDINGS = Path.home() / ".config/hypr/bindings.lua"
STATE_DIR = Path.home() / ".local/state/blackdrop"
STATE_MARKER = STATE_DIR / "applied"

BLOCK_START = "-- BLACKDROP START"
BLOCK_END = "-- BLACKDROP END"

REQUIRED_SCRIPTS = (
    "audio-watch.py",
    "projectm-key.py",
    "run-projectm.sh",
    "set_projectm_fps.py",
    "wait-projectm.py",
)

PROJECTM_BINARY = "projectM-pulseaudio"
PACKAGE_HELPER = "omarchy-pkg-add"
PACKAGES = ("projectm", "projectm-pulseaudio")
TERMINAL_LAUNCHER = Path("/usr/bin/omarchy-launch-floating-terminal-with-presentation")

# Every read below is bounded and refuses to follow a symlink, so a replaced
# configuration file cannot make this probe stream without limit.
READ_LIMIT = 256 * 1024


def read_limited(path: Path, limit: int = READ_LIMIT) -> str:
    """Return at most `limit` bytes of a regular file, or '' when unavailable."""
    flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        handle = os.open(path, flags)
    except OSError:
        return ""
    try:
        if not stat.S_ISREG(os.fstat(handle).st_mode):
            return ""
        data = os.read(handle, limit)
    except OSError:
        return ""
    finally:
        os.close(handle)
    return data.decode("utf-8", "replace")


def projectm_binary() -> str:
    found = shutil.which(PROJECTM_BINARY)
    if found:
        return found
    for candidate in (f"/usr/bin/{PROJECTM_BINARY}", f"/usr/local/bin/{PROJECTM_BINARY}"):
        if os.access(candidate, os.X_OK):
            return candidate
    return ""


def config_value(text: str, key: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(key) and "=" in stripped:
            return stripped.split("=", 1)[1].strip()
    return ""


def presets_present() -> int:
    try:
        return sum(1 for entry in PRESETS_DIR.glob("*.milk") if entry.is_file())
    except OSError:
        return 0


def manifest_version() -> str:
    try:
        parsed = json.loads(read_limited(PLUGIN_DIR / "manifest.json", 64 * 1024) or "{}")
    except ValueError:
        return "unknown"
    version = parsed.get("version")
    return str(version) if version else "unknown"


def collect_checks() -> dict[str, bool]:
    configured = config_value(read_limited(USER_CONFIG), "Preset Path")
    bindings = read_limited(BINDINGS)
    return {
        "projectm_binary": bool(projectm_binary()),
        "projectm_base_config": BASE_CONFIG.is_file(),
        "plugin_scripts": all(
            os.access(PLUGIN_DIR / "scripts" / name, os.X_OK) for name in REQUIRED_SCRIPTS
        ),
        "presets": presets_present() > 0,
        "preset_path": bool(configured) and Path(configured) == PRESETS_DIR,
        "bindings_block": BLOCK_START in bindings and BLOCK_END in bindings,
        "setup_state": STATE_MARKER.is_file(),
        "terminal_launcher": TERMINAL_LAUNCHER.is_file(),
        "package_helper": shutil.which(PACKAGE_HELPER) is not None,
    }


# Dependency order: fixing an earlier reason is what unblocks the later ones.
REASONS = (
    (
        "projectm_binary",
        f"The projectM visualizer is not installed. Its repository package ({PACKAGES[1]}) "
        "provides the window Blackdrop renders into.",
    ),
    (
        "projectm_base_config",
        "projectM's default configuration is missing, which means its packages are not "
        "installed yet.",
    ),
    (
        "plugin_scripts",
        "Blackdrop's helper scripts are missing or not executable in this checkout.",
    ),
    (
        "presets",
        "Blackdrop's curated preset folder is empty in this checkout.",
    ),
    (
        "preset_path",
        "Blackdrop's curated preset path is not applied to projectM's configuration yet.",
    ),
    (
        "bindings_block",
        "The Super+Shift+B toggle and the projectM window rules are not applied yet.",
    ),
)

READY_KEYS = (
    "projectm_binary",
    "projectm_base_config",
    "plugin_scripts",
    "presets",
    "preset_path",
    "bindings_block",
)


def build_payload() -> dict:
    checks = collect_checks()
    return {
        "schema": 1,
        "plugin": "io.github.jcarcinogen.blackdrop",
        "version": manifest_version(),
        "ready": all(checks.get(key) is True for key in READY_KEYS),
        "checks": checks,
        "reasons": [message for key, message in REASONS if checks.get(key) is not True],
        "preset_count": presets_present(),
        "plugin_dir": str(PLUGIN_DIR),
        "setup_command": str(PLUGIN_DIR / "setup.sh"),
        "package_step": " ".join((PACKAGE_HELPER, *PACKAGES)),
        "setup_available": checks["terminal_launcher"] is True,
    }


def print_human(payload: dict) -> None:
    state = "ready" if payload["ready"] else "setup required"
    print(f"Blackdrop {payload['version']}: {state}")
    for key, value in payload["checks"].items():
        print(f"  [{'ok' if value else '--'}] {key}")
    if payload["ready"]:
        return
    print()
    print("Still needed:")
    for reason in payload["reasons"]:
        print(f"  - {reason}")
    print()
    print(f"Run this once: {payload['setup_command']}")


def main(argv: list[str]) -> int:
    payload = build_payload()
    if "--json" in argv:
        print(json.dumps(payload))
    else:
        print_human(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
