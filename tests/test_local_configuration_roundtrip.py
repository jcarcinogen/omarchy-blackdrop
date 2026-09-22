"""Round-trip tests for the reversible local configuration.

`install-local.py` and `remove-local.py` are the only files that touch a user's
configuration. These tests run them against a temporary HOME and assert the
properties a marketplace reviewer cares about: they write only what they claim
to, they edit the file projectM itself opens, and removing the plugin restores
the user's own files exactly — including the old path that 0.2.0 wrote.
"""

import contextlib
import importlib.util
import io
import unittest
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLOCK_START = "-- BLACKDROP START"
BLOCK_END = "-- BLACKDROP END"
USER_LINE = 'hl.bind("SUPER + RETURN", hl.dsp.exec_cmd("foot"))\n'
USER_CONFIG = "FPS  = 30\nPreset Path = /usr/share/projectM/presets\nFullscreen  = true\n"
USER_CONFIG_CRLF = (
    b"Mesh X  = 220\t\t\t# Width of PerPixel Equation mesh\r\n"
    b"FPS  = 30\r\n"
    b"Preset Path = /usr/share/projectM/presets\r\n"
    b"Fullscreen  = true\r\n"
    b"# a line we never touch\r\n"
)


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
        # The path projectM opens, and the path 0.2.0 wrote.
        self.projectm_config = self.home / ".projectM/config.inp"
        self.legacy_config = self.home / ".config/projectM/config.inp"
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
            module.LEGACY_CONFIG = self.legacy_config
            module.BINDINGS = self.binding_file
        self.install.MARKER = self.state / "applied"
        self.install.BASE_CONFIG = self.base_config
        self.backup = self.state / self.install.BACKUP_NAME
        self.absent = self.state / self.install.ABSENT_NAME

    def apply(self) -> None:
        self.install.configure_projectm()
        self.install.configure_hyprland()
        self.install.record_state()

    def remove_all(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()):
            self.remove.main()

    def legacy_apply(self) -> None:
        """Leave behind what 0.2.0 would have written, state files included."""
        self.legacy_config.parent.mkdir(parents=True, exist_ok=True)
        self.legacy_config.write_text(USER_CONFIG, encoding="utf-8")
        self.state.mkdir(parents=True, exist_ok=True)
        (self.state / self.install.LEGACY_BACKUP_NAME).write_text(USER_CONFIG, encoding="utf-8")

    # --- install -----------------------------------------------------------

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
        self.assertEqual(self.backup.read_text(encoding="utf-8"), USER_CONFIG)

    def test_install_targets_the_path_projectm_actually_opens(self):
        self.apply()
        self.assertIn(f"Preset Path = {ROOT / 'presets'}", self.projectm_config.read_text("utf-8"))
        # The old path is not created when it did not exist.
        self.assertFalse(self.legacy_config.exists())

    def test_install_preserves_line_endings_and_other_lines(self):
        self.projectm_config.write_bytes(USER_CONFIG_CRLF)
        self.apply()

        data = self.projectm_config.read_bytes()
        self.assertIn(b"FPS  = 60                 # Frames Per Second\r\n", data)
        self.assertIn(b"Mesh X  = 220\t\t\t# Width of PerPixel Equation mesh\r\n", data)
        self.assertIn(b"# a line we never touch\r\n", data)
        # No bare LF was introduced anywhere in a CRLF file.
        self.assertEqual(data.count(b"\n"), data.count(b"\r\n"))

    def test_install_creates_the_config_from_the_package_default_when_missing(self):
        self.projectm_config.unlink()
        self.apply()
        config = self.projectm_config.read_text(encoding="utf-8")
        self.assertNotIn("FPS  = 30", config)
        self.assertIn("FPS  = 60", config)
        self.assertIn(f"Preset Path = {ROOT / 'presets'}", config)
        # We created it, so removal may delete it again.
        self.assertTrue(self.absent.is_file())
        self.assertFalse(self.backup.exists())

    def test_install_is_idempotent(self):
        self.apply()
        first = self.binding_file.read_text(encoding="utf-8")
        self.apply()
        second = self.binding_file.read_text(encoding="utf-8")
        self.assertEqual(first, second)
        self.assertEqual(second.count(BLOCK_START), 1)
        # The backup must still hold the user's original, not our own output.
        self.assertEqual(self.backup.read_text(encoding="utf-8"), USER_CONFIG)

    # --- the 0.2.0 path ----------------------------------------------------

    def test_install_removes_a_legacy_config_it_created(self):
        self.state.mkdir(parents=True, exist_ok=True)
        (self.state / self.install.LEGACY_ABSENT_NAME).touch()
        self.legacy_config.parent.mkdir(parents=True, exist_ok=True)
        self.legacy_config.write_text(USER_CONFIG, encoding="utf-8")

        self.apply()

        self.assertFalse(self.legacy_config.exists())
        self.assertFalse((self.state / self.install.LEGACY_ABSENT_NAME).exists())

    def test_install_restores_a_user_legacy_config(self):
        self.legacy_apply()

        self.apply()

        self.assertEqual(self.legacy_config.read_text(encoding="utf-8"), USER_CONFIG)
        self.assertFalse((self.state / self.install.LEGACY_BACKUP_NAME).exists())

    def test_install_leaves_an_unrecorded_legacy_config_alone(self):
        self.legacy_config.parent.mkdir(parents=True, exist_ok=True)
        self.legacy_config.write_text("# someone else's file\n", encoding="utf-8")

        self.apply()

        self.assertEqual(self.legacy_config.read_text(encoding="utf-8"), "# someone else's file\n")

    # --- removal -----------------------------------------------------------

    def test_remove_restores_user_files_and_leaves_no_owned_state(self):
        self.apply()
        self.remove_all()

        self.assertEqual(self.binding_file.read_text(encoding="utf-8").strip(), USER_LINE.strip())
        self.assertEqual(self.projectm_config.read_text(encoding="utf-8"), USER_CONFIG)
        self.assertFalse(self.backup.exists())
        self.assertFalse((self.state / "applied").exists())

    def test_remove_retires_a_legacy_config(self):
        self.legacy_apply()
        self.apply()
        self.remove_all()

        self.assertEqual(self.legacy_config.read_text(encoding="utf-8"), USER_CONFIG)
        self.assertFalse((self.state / self.install.LEGACY_BACKUP_NAME).exists())

    def test_remove_deletes_a_config_it_created(self):
        self.projectm_config.unlink()
        self.apply()
        self.remove_all()
        self.assertFalse(self.projectm_config.exists())

    def test_remove_preserves_unknown_state_files(self):
        self.apply()
        stray = self.state / "user-notes.txt"
        stray.write_text("keep me", encoding="utf-8")
        self.remove_all()
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
