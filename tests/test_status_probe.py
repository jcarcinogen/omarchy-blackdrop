"""Behavioural tests for the read-only status probe.

The probe is what the plugin trusts to decide between showing the visualizer and
showing the setup card, so it is tested both ways: a fresh marketplace install
(everything missing) and a fully configured machine (ready), plus the guarantee
that it never writes anything.
"""

import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "scripts/status.py"


def load_status():
    spec = importlib.util.spec_from_file_location("blackdrop_status_probe", STATUS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def tree_snapshot(root: Path) -> set:
    return {str(path.relative_to(root)) for path in root.rglob("*")}


class FreshMarketplaceInstallTests(unittest.TestCase):
    """Everything the one-time setup provides is absent, as after `plugin add`."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.home = Path(self._tmp.name)
        self.module = load_status()
        self.module.USER_CONFIG = self.home / ".projectM/config.inp"
        self.module.BINDINGS = self.home / ".config/hypr/bindings.lua"
        self.module.STATE_MARKER = self.home / ".local/state/blackdrop/applied"
        self.module.BASE_CONFIG = self.home / "no-such-projectm-base"
        self.module.TERMINAL_LAUNCHER = self.home / "no-such-launcher"

    def test_reports_not_ready_and_names_the_missing_pieces(self):
        payload = self.module.build_payload()
        self.assertFalse(payload["ready"])
        self.assertFalse(payload["checks"]["projectm_base_config"])
        self.assertFalse(payload["checks"]["preset_path"])
        self.assertFalse(payload["checks"]["bindings_block"])
        self.assertFalse(payload["checks"]["setup_state"])
        joined = " ".join(payload["reasons"])
        self.assertIn("projectM visualizer is not installed", joined)
        self.assertIn("Super+Shift+B", joined)

    def test_probe_writes_nothing(self):
        before = tree_snapshot(self.home)
        self.module.build_payload()
        self.assertEqual(tree_snapshot(self.home), before)

    def test_cli_emits_parseable_json_and_exits_zero(self):
        result = subprocess.run(
            [sys.executable, str(STATUS), "--json"],
            capture_output=True,
            text=True,
            check=False,
            env=dict(os.environ, HOME=str(self.home)),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["schema"], 1)
        self.assertIn("checks", payload)


class PreparedMachineTests(unittest.TestCase):
    """The same probe on a machine where setup has already succeeded."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.home = Path(self._tmp.name)
        self.module = load_status()

        bin_dir = self.home / "bin"
        bin_dir.mkdir()
        fake = bin_dir / "projectM-pulseaudio"
        fake.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        self._old_path = os.environ["PATH"]
        os.environ["PATH"] = str(bin_dir) + os.pathsep + self._old_path
        self.addCleanup(lambda: os.environ.__setitem__("PATH", self._old_path))

        base = self.home / "projectm-base.inp"
        base.write_text("FPS  = 60\nPreset Path = /usr/share/projectM/presets\n", encoding="utf-8")

        config = self.home / ".projectM/config.inp"
        config.parent.mkdir(parents=True)
        config.write_text(f"Preset Path = {ROOT / 'presets'}\n", encoding="utf-8")

        bindings = self.home / ".config/hypr/bindings.lua"
        bindings.parent.mkdir(parents=True)
        bindings.write_text("-- BLACKDROP START\n-- BLACKDROP END\n", encoding="utf-8")

        marker = self.home / ".local/state/blackdrop/applied"
        marker.parent.mkdir(parents=True)
        marker.write_text("version=0.2.0\n", encoding="utf-8")

        self.module.USER_CONFIG = config
        self.module.BINDINGS = bindings
        self.module.STATE_MARKER = marker
        self.module.BASE_CONFIG = base
        self.module.TERMINAL_LAUNCHER = ROOT / "README.md"

    def test_reports_ready_with_no_reasons(self):
        payload = self.module.build_payload()
        self.assertTrue(payload["ready"], payload)
        self.assertEqual(payload["reasons"], [])
        self.assertTrue(all(payload["checks"][key] for key in self.module.READY_KEYS))
        self.assertTrue(payload["setup_available"])
        self.assertEqual(payload["preset_count"], 12)
        # package_helper and terminal_launcher describe the setup path only, so a
        # machine that is already configured stays ready without them.
        self.assertNotIn("package_helper", self.module.READY_KEYS)

    def test_probe_writes_nothing_when_ready(self):
        before = tree_snapshot(self.home)
        self.module.build_payload()
        self.assertEqual(tree_snapshot(self.home), before)


if __name__ == "__main__":
    unittest.main()
