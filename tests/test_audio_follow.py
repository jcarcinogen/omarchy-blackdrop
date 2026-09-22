"""Tests that Blackdrop keeps projectM listening to the device that is playing.

Field failure this pins down (Acer Swift Go 14, 2026-09-22): PipeWire's
stream-restore remembered projectM's capture target as the headset source, so
projectM received silence while music played on the USB-C adapter and rendered
its idle logo screen — which looks exactly like a plugin that does not work.
The fixtures below are captured from that machine's `pactl -f json` output.
"""

import contextlib
import importlib.util
import io
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MONITOR = (
    "alsa_output.usb-Apple__Inc._USB-C_to_3.5mm_Headphone_Jack_Adapter_DWH53260DPY2FN3AQ-00"
    ".analog-stereo.monitor"
)
SINK = MONITOR[: -len(".monitor")]
HEADSET = "alsa_input.pci-0000_00_1f.3-platform-sof_sdw.HiFi__Headset__source"

SOURCES = [
    {"index": 290, "name": "alsa_output.pci-0000_00_1f.3-platform-sof_sdw.HiFi__Speaker__sink.monitor"},
    {"index": 292, "name": "alsa_output.pci-0000_00_1f.3-platform-sof_sdw.HiFi__HDMI1__sink.monitor"},
    {"index": 296, "name": HEADSET},
    {"index": 6617, "name": MONITOR},
]

# Verbatim shape of the live capture from omarchy-acer.
PROJECTM_ON_HEADSET = {
    "index": 7640,
    "source": 296,
    "properties": {
        "application.name": "projectM",
        "application.process.binary": "projectM-pulseaudio",
        "target.object": HEADSET,
    },
}
PROJECTM_ON_MONITOR = {
    "index": 7641,
    "source": 6617,
    "properties": {
        "application.name": "projectM",
        "application.process.binary": "projectM-pulseaudio",
        "target.object": MONITOR,
    },
}
RECORDER_STREAM = {
    "index": 7642,
    "source": 6617,
    "properties": {"application.name": "parec", "application.process.binary": "parec"},
}


def load_watcher():
    spec = importlib.util.spec_from_file_location("blackdrop_audio_watch", ROOT / "scripts/audio-watch.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeRun:
    """Stands in for subprocess.run and records the commands that were issued."""

    def __init__(self, streams, sources=None, fail_on=(), sink=SINK):
        self.streams = streams
        self.sources = SOURCES if sources is None else sources
        self.fail_on = fail_on
        self.sink = sink
        self.calls = []

    def __call__(self, argv, **_kwargs):
        self.calls.append(list(argv))
        if argv in self.fail_on:
            raise RuntimeError("pactl: command failed")
        if argv[1:] == ["get-default-sink"]:
            stdout = self.sink + "\n"
        elif argv[3:] == ["list", "source-outputs"]:
            stdout = json.dumps(self.streams)
        elif argv[3:] == ["list", "sources"]:
            stdout = json.dumps(self.sources)
        else:
            stdout = ""
        return type("Result", (), {"stdout": stdout, "returncode": 0})()

    @property
    def moves(self):
        return [call for call in self.calls if call[:2] == ["pactl", "move-source-output"]]

    @property
    def listings(self):
        return [call for call in self.calls if call[3:] == ["list", "source-outputs"]]


class CaptureAlignmentTests(unittest.TestCase):
    def setUp(self):
        self.watcher = load_watcher()
        self.names = {source["index"]: source["name"] for source in SOURCES}

    def test_capture_on_a_stale_device_is_moved(self):
        moves = self.watcher.captures_to_move([PROJECTM_ON_HEADSET], self.names, MONITOR)
        self.assertEqual(moves, [7640])

    def test_capture_already_on_the_playing_sink_is_left_alone(self):
        moves = self.watcher.captures_to_move([PROJECTM_ON_MONITOR], self.names, MONITOR)
        self.assertEqual(moves, [])

    def test_other_apps_are_never_moved(self):
        moves = self.watcher.captures_to_move([RECORDER_STREAM], self.names, MONITOR)
        self.assertEqual(moves, [])

    def test_every_projectm_capture_is_moved(self):
        second = dict(PROJECTM_ON_HEADSET, index=7643)
        moves = self.watcher.captures_to_move(
            [PROJECTM_ON_HEADSET, RECORDER_STREAM, second], self.names, MONITOR
        )
        self.assertEqual(moves, [7640, 7643])

    def test_target_object_is_used_when_the_index_is_unknown(self):
        self.assertEqual(self.watcher.captures_to_move([PROJECTM_ON_HEADSET], {}, MONITOR), [7640])
        unconnected = dict(PROJECTM_ON_HEADSET, source=None)
        self.assertEqual(self.watcher.captures_to_move([unconnected], {}, MONITOR), [7640])
        on_monitor = dict(PROJECTM_ON_HEADSET, source=None, properties=dict(PROJECTM_ON_HEADSET["properties"], **{"target.object": MONITOR}))
        self.assertEqual(self.watcher.captures_to_move([on_monitor], {}, MONITOR), [])

    def test_align_capture_issues_the_move_for_the_playing_sink(self):
        run = FakeRun([PROJECTM_ON_HEADSET])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            moved = self.watcher.align_capture(MONITOR, run=run)
        self.assertEqual(moved, [7640])
        self.assertEqual(run.moves, [["pactl", "move-source-output", "7640", MONITOR]])
        self.assertIn("capture:" + MONITOR, out.getvalue())

    def test_align_capture_is_silent_when_nothing_needs_moving(self):
        run = FakeRun([PROJECTM_ON_MONITOR, RECORDER_STREAM])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(self.watcher.align_capture(MONITOR, run=run), [])
        self.assertEqual(run.moves, [])
        self.assertEqual(out.getvalue(), "")

    def test_sources_failure_still_allows_alignment(self):
        """Source names are a convenience; target.object can carry the decision."""
        run = FakeRun([PROJECTM_ON_HEADSET], fail_on=[["pactl", "-f", "json", "list", "sources"]])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(self.watcher.align_capture(MONITOR, run=run), [7640])

    def test_align_capture_never_raises_when_listing_fails(self):
        run = FakeRun([], fail_on=[["pactl", "-f", "json", "list", "source-outputs"]])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(self.watcher.align_capture(MONITOR, run=run), [])
        self.assertIn("capture-error:", out.getvalue())

    def test_a_failed_move_is_reported_and_does_not_stop_the_watcher(self):
        run = FakeRun([PROJECTM_ON_HEADSET], fail_on=[["pactl", "move-source-output", "7640", MONITOR]])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(self.watcher.align_capture(MONITOR, run=run), [])
        self.assertIn("capture-error:", out.getvalue())

    def test_align_once_stops_as_soon_as_the_capture_is_moved(self):
        run = FakeRun([PROJECTM_ON_HEADSET])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(self.watcher.align_once(attempts=6, pause=0, run=run), 0)
        self.assertEqual(run.moves, [["pactl", "move-source-output", "7640", MONITOR]])
        self.assertEqual(len(run.listings), 1)

    def test_align_once_gives_up_after_its_attempts(self):
        run = FakeRun([PROJECTM_ON_MONITOR])  # already correct: nothing to move
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(self.watcher.align_once(attempts=3, pause=0, run=run), 0)
        self.assertEqual(run.moves, [])
        self.assertEqual(len(run.listings), 3)

    def test_align_once_reports_a_missing_audio_server(self):
        run = FakeRun([], fail_on=[["pactl", "get-default-sink"]])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(self.watcher.align_once(attempts=2, pause=0, run=run), 1)
        self.assertIn("capture-error:", out.getvalue())


if __name__ == "__main__":
    unittest.main()
