"""Contract tests for the marketplace install path.

These encode the regression that motivated 0.2.0: a marketplace install only
clones this repository, so the plugin must be able to (a) detect that the
projectM packages and its reversible local configuration are missing and
(b) name one visible step that fixes it. Nothing may change user configuration
before that step runs, and nothing may request elevated privileges.
"""

import importlib.util
import json
import os
import stat
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))

# Assembled at runtime so this file never contains the token it forbids.
PRIVILEGE_WORDS = ("su" + "do", "pk" + "exec")

TEXT_SUFFIXES = {".py", ".sh", ".qml", ".md", ".json", ".yml", ".yaml", ".js", ".txt"}
SKIP_DIRS = {".git", "__pycache__"}


def load_module(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MarketplaceContractTests(unittest.TestCase):
    def test_manifest_is_listable(self):
        self.assertEqual(MANIFEST["schemaVersion"], 1)
        self.assertEqual(MANIFEST["id"], "io.github.jcarcinogen.blackdrop")
        self.assertFalse(MANIFEST["id"].startswith("omarchy."))
        self.assertTrue(MANIFEST["author"])
        self.assertTrue(MANIFEST["description"])
        # The marketplace card copy is capped at about 500 characters.
        self.assertLessEqual(len(MANIFEST["description"]), 500)

    def test_entry_points_exist(self):
        for kind, relative in MANIFEST["entryPoints"].items():
            with self.subTest(kind=kind):
                self.assertTrue((ROOT / relative).is_file(), relative)

    def test_setup_entry_points_are_present_and_executable(self):
        for relative in ("setup.sh", "install-local.py", "remove-local.py", "scripts/status.py"):
            with self.subTest(path=relative):
                path = ROOT / relative
                self.assertTrue(path.is_file(), relative)
                self.assertTrue(path.stat().st_mode & stat.S_IXUSR, f"{relative} is not executable")

    def test_setup_script_installs_packages_then_applies_configuration(self):
        text = (ROOT / "setup.sh").read_text(encoding="utf-8")
        self.assertIn("omarchy-pkg-add projectm projectm-pulseaudio", text)
        self.assertIn("install-local.py", text)
        self.assertIn("scripts/status.py", text)
        # The FPS helper reads projectM's config, so the packages must come first.
        self.assertLess(text.index("omarchy-pkg-add"), text.index("install-local.py"))

    def test_plugin_never_requests_elevated_privileges(self):
        offenders = []
        for path in ROOT.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            if SKIP_DIRS.intersection(path.parts):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
            for word in PRIVILEGE_WORDS:
                if word in text:
                    offenders.append(f"{path.relative_to(ROOT)}: {word}")
        self.assertEqual(offenders, [], "plugin files must not carry a privilege boundary")

    def test_status_probe_reports_the_marketplace_gap(self):
        module = load_module("blackdrop_status", "scripts/status.py")
        payload = module.build_payload()
        self.assertEqual(payload["schema"], 1)
        self.assertIn("setup_command", payload)
        self.assertTrue(payload["setup_command"].endswith("setup.sh"))
        self.assertEqual(payload["package_step"], "omarchy-pkg-add projectm projectm-pulseaudio")
        self.assertEqual(
            sorted(payload["checks"]),
            sorted(
                [
                    "projectm_binary",
                    "projectm_base_config",
                    "plugin_scripts",
                    "presets",
                    "preset_path",
                    "bindings_block",
                    "setup_state",
                    "terminal_launcher",
                    "package_helper",
                ]
            ),
        )
        self.assertEqual(payload["ready"], all(payload["checks"][key] for key in module.READY_KEYS))

    def test_overlay_offers_the_visible_setup_path(self):
        text = (ROOT / "Overlay.qml").read_text(encoding="utf-8")
        self.assertIn("Blackdrop Setup Required", text)
        self.assertIn("Open Setup Terminal", text)
        self.assertIn("Copy setup command", text)
        # The setup card must not be behind the click-swallowing visualizer area.
        self.assertIn("visible: !root.setupRequired", text)

    def test_setup_action_steps_the_overlay_aside(self):
        """A layer-shell Overlay always sits above ordinary windows.

        Launching the setup terminal without hiding the overlay first leaves the
        whole hand-off invisible, which is the bug this contract pins down.
        """
        text = (ROOT / "Overlay.qml").read_text(encoding="utf-8")
        self.assertIn("WlrLayershell.layer: WlrLayer.Overlay", text)
        self.assertIn("function dismiss()", text)
        self.assertIn("shell.hide(pluginId)", text)
        self.assertIn("if (root.session.openSetupTerminal()) root.dismiss()", text)

    def test_service_probe_path_is_wired(self):
        text = (ROOT / "Service.qml").read_text(encoding="utf-8")
        self.assertIn("scripts/status.py", text)
        self.assertIn("omarchy-launch-floating-terminal-with-presentation", text)
        self.assertIn("setupRequired", text)
        # Nothing may start the visualizer before the probe says the machine is ready.
        self.assertIn("if (!monitorProc.running) monitorProc.running = true", text)


if __name__ == "__main__":
    unittest.main()
