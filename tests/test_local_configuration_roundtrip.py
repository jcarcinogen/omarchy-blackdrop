"""Round-trip tests for the reversible local configuration.

`install-local.py` and `remove-local.py` are the only files that touch a user's
configuration. These tests run them against a temporary HOME and assert the two
properties a marketplace reviewer cares about: they write only what they claim
to, and removing the plugin restores the user's own files exactly.
"""

import importlib.util
import unittest
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLOCK_START = "-- BLACKDROP START"
BLOCK_END = "-- BLACKDROP END"
USER_LINE = 'hl.bind("SUPER + RETURN", hl.dsp.exec_cmd("foot"))\n'
USER_CONFIG = "FPS  = 30\nPreset Path = /usr/share/projectM/presets\nFullscreen  = true\n"


def load_module(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LocalConfigurationRoundTripTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.home = Path(self._tmp.name)
        self.state = self.home / ".local/state/blackdrop"
        self.binding_file = self.home / ".config/hypr/bindings.lua"
        self.projectm_config = self.home / ".config/projectM/config.inp"
        self.base_config = self.home / "projectm-base.inp"

        self.base_config.write_text(USER_CONFIG, encoding="utf-8")
        self.projectm_config.parent.mkdir(parents=True)
        self.projectm_config.write_text(USER_CONFIG, encoding="utf-8")
        self.binding_file.parent.mkdir(parents=True)
        self.binding_file.write_text(USER_LINE, encoding="utf-8")

        self.install = load_module("blackdrop_install_local", "install-local.py")
        self.remove = load_module("blackdrop_remove_local", "remove-local.py")
        for module in (self.install, self.remove):
            module.STATE = self.state
            module.CONFIG = self.projectm_config
            module.BINDINGS = self.binding_file
        self.install.MARKER = self.state / "applied"
        self.install.BASE_CONFIG = self.base_config

    def apply(self) -> None:
        self.install.configure_projectm()
        self.install.configure_hyprland()
        self.install.record_state()

    def test_install_writes_only_its_own_state(self):
        self.apply()

        config = self.projectm_config.read_text(encoding="utf-8")
        self.assertIn(f"Preset Path = {ROOT / 'presets'}", config)
        self.assertIn("FPS  = 60", config)
        self.assertIn("Hard Cut Sensitivity = 3", config)
        self.assertIn("Preset Duration = 86400", config)
        self.assertIn("Fullscreen  = false", config)

        bindings = self.binding_file.read_text(encoding="utf-8")
        self.assertIn(USER_LINE.strip(), bindings)
        self.assertEqual(bindings.count(BLOCK_START), 1)
        self.assertEqual(bindings.count(BLOCK_END), 1)
        self.assertIn("SUPER + SHIFT + B", bindings)

        self.assertTrue((self.state / "applied").is_file())
        self.assertEqual(
            (self.state / "config.inp.before-blackdrop").read_text(encoding="utf-8"), USER_CONFIG
        )

    def test_install_is_idempotent(self):
        self.apply()
        first = self.binding_file.read_text(encoding="utf-8")
        self.apply()
        second = self.binding_file.read_text(encoding="utf-8")
        self.assertEqual(first, second)
        self.assertEqual(second.count(BLOCK_START), 1)
        # The backup must still hold the user's original, not our own output.
        self.assertEqual(
            (self.state / "config.inp.before-blackdrop").read_text(encoding="utf-8"), USER_CONFIG
        )

    def test_remove_restores_user_files_and_leaves_no_owned_state(self):
        self.apply()
        self.remove.remove_bindings_block()
        self.remove.restore_projectm_config()
        (self.state / "applied").unlink()
        (self.state / "projectm-config-was-absent").unlink(missing_ok=True)
        (self.state / "config.inp.before-blackdrop").unlink()

        self.assertEqual(self.binding_file.read_text(encoding="utf-8").strip(), USER_LINE.strip())
        self.assertEqual(self.projectm_config.read_text(encoding="utf-8"), USER_CONFIG)

    def test_remove_preserves_unknown_state_files(self):
        self.apply()
        stray = self.state / "user-notes.txt"
        stray.write_text("keep me", encoding="utf-8")
        self.remove.main()
        self.assertTrue(stray.is_file())
        self.assertTrue(self.state.is_dir())

    def test_install_refuses_without_the_projectm_packages(self):
        self.base_config.unlink()
        self.projectm_config.unlink()
        with self.assertRaises(SystemExit) as raised:
            self.install.configure_projectm()
        self.assertIn("projectM packages", str(raised.exception))
        # A refusal must not leave a half-written configuration behind.
        self.assertFalse(self.projectm_config.exists())


if __name__ == "__main__":
    unittest.main()
